"""The A2A cycle: scan → decide → reach out → recommend.

This is the owner-facing brain that sits on top of the existing discovery /
compatibility engine. One cycle:

  1. Sync the agent's profile (tags + goals).
  2. Discover candidate agents (excluding self, same-owner, already-connected).
  3. Ask Gemini, per candidate, *who* is worth knowing and *how* to connect
     (dm / follow / comment / skip) — Task 2 of the A2A spec.
  4. Autonomously act on the best fits while the owner is offline:
       - one DM (a full intro↔response interaction via the a2a_engine), and
       - up to a couple of follows.
  5. Persist a short ranked list of `agent_recommendations` for the owner —
     "people you should meet" with a one-line why (Task 3).

Everything is logged loudly (Task 5) so a dev can watch what the agent decided
and why. The same `run_a2a_cycle` is called by the manual POST /run-a2a endpoint
and by the 6-hourly `network_scan` scheduler job.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import (
    ActivityType,
    Agent,
    AgentFollow,
    AgentRecommendation,
)
from app.models.agent import AgentMemoryType
from app.models.interaction import ConnectionType
from app.prompts.templates import A2A_OUTREACH_DECISION
from app.services.a2a import can_initiate
from app.services.a2a_engine import already_connected, log_discovery, run_interaction
from app.services.activity_logger import log_activity
from app.services.agent_service import add_memory
from app.services.compatibility import compute_compatibility
from app.services.gemini import generate
from app.services.profile_sync import sync_agent_profile, upsert_connection

logger = get_logger("axolot.a2a_reco")

# Tunables — product decisions, kept here next to the logic they govern.
MAX_RECOMMENDATIONS = 5
MAX_SCAN = 60            # cap agents scored per cycle (bounds Gemini cost)
DECISION_POOL = 8        # how many top candidates Gemini judges per cycle
DM_SCORE_FLOOR = 40.0    # min compatibility to autonomously DM the best fit
FOLLOW_SCORE_FLOOR = 28.0
MAX_FOLLOWS_PER_CYCLE = 2
VALID_ACTIONS = {"dm", "follow", "comment", "skip"}


# ── Gemini decision ──────────────────────────────────────────────────────────
def _rule_action(score: float) -> str:
    """Deterministic fallback when Gemini is unavailable or malformed."""
    if score >= DM_SCORE_FLOOR:
        return "dm"
    if score >= FOLLOW_SCORE_FLOOR:
        return "follow"
    return "comment"


def _candidates_block(candidates: list[tuple[Agent, dict]]) -> str:
    lines = []
    for i, (other, compat) in enumerate(candidates, start=1):
        uname = other.user.name if other.user else other.name
        lines.append(
            f"{i}. {other.name} (agent of {uname}) — "
            f"goals: {other.goal_titles or '—'}; "
            f"interests: {other.interest_tags or '—'}; "
            f"compatibility {compat['score']:.0f}/100 "
            f"(shared: {compat.get('shared_goals') or '—'})"
        )
    return "\n".join(lines)


def decide_outreach(
    db: Session, agent: Agent, candidates: list[tuple[Agent, dict]]
) -> list[dict]:
    """Per-candidate decision: {agent, compat, action, recommend, reason}.

    Asks Gemini once for the whole pool; falls back to score-based rules per
    candidate on any parse/transport failure so a cycle never dies here.
    """
    if not candidates:
        return []

    decisions_by_index: dict[int, dict] = {}
    try:
        prompt = A2A_OUTREACH_DECISION.format(
            agent_name=agent.name,
            user_name=agent.user.name if agent.user else "your user",
            goals=agent.goal_titles or [],
            personality=agent.personality_vector or {},
            candidates_block=_candidates_block(candidates),
        )
        raw = generate(prompt, response_format="a2a_decision")
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            for pos, item in enumerate(parsed, start=1):
                if not isinstance(item, dict):
                    continue
                idx = int(item.get("index", pos))
                decisions_by_index[idx] = item
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        log_event(logger, "a2a_decision_parse_failed", agent_id=agent.id, error=str(exc))

    out: list[dict] = []
    for i, (other, compat) in enumerate(candidates, start=1):
        raw_item = decisions_by_index.get(i, {})
        action = str(raw_item.get("action", "")).lower().strip()
        if action not in VALID_ACTIONS:
            action = _rule_action(compat["score"])
        reason = (raw_item.get("reason") or "").strip() or compat.get("reason", "")
        recommend = raw_item.get("recommend_to_owner")
        if recommend is None:
            recommend = action != "skip"
        out.append({
            "agent": other,
            "compat": compat,
            "action": action,
            "recommend": bool(recommend),
            "reason": reason,
        })
    return out


# ── Actions the agent can take autonomously ──────────────────────────────────
def _follow(db: Session, agent: Agent, other: Agent) -> bool:
    """Idempotent follow. Returns True only when a new edge was created."""
    existing = (
        db.query(AgentFollow)
        .filter(
            AgentFollow.follower_agent_id == agent.id,
            AgentFollow.following_agent_id == other.id,
        )
        .first()
    )
    if existing:
        return False
    db.add(AgentFollow(follower_agent_id=agent.id, following_agent_id=other.id))
    db.commit()
    return True


def _gather_candidates(db: Session, agent: Agent) -> list[tuple[Agent, dict]]:
    candidates: list[tuple[Agent, dict]] = []
    needs_commit = False
    for other in db.query(Agent).filter(Agent.id != agent.id).all():
        if len(candidates) >= MAX_SCAN:
            break
        if not other.user or other.user_id == agent.user_id:
            continue
        if already_connected(db, agent.id, other.id):
            continue
        # Candidates' goals/tags live on the user until synced — pull them onto
        # the agent so goal-alignment scoring has something to work with.
        sync_agent_profile(db, other, commit=False)
        needs_commit = True
        candidates.append((other, compute_compatibility(agent, other)))
    if needs_commit:
        db.commit()
    candidates.sort(key=lambda c: c[1]["score"], reverse=True)
    return candidates


# ── Recommendations ──────────────────────────────────────────────────────────
def _has_unseen_rec(db: Session, agent_id: str, target_agent_id: str) -> bool:
    return (
        db.query(AgentRecommendation)
        .filter(
            AgentRecommendation.agent_id == agent_id,
            AgentRecommendation.recommended_agent_id == target_agent_id,
            AgentRecommendation.seen == False,  # noqa: E712
        )
        .first()
        is not None
    )


def _rec_dict(r: AgentRecommendation) -> dict:
    return {
        "id": r.id,
        "recommended_user_id": r.recommended_user_id,
        "recommended_agent_id": r.recommended_agent_id,
        "recommended_name": r.recommended_name,
        "reason": r.reason,
        "compatibility_score": r.compatibility_score,
        "suggested_action": r.suggested_action,
        "seen": r.seen,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def generate_recommendations(
    db: Session, agent: Agent, decisions: list[dict], limit: int = MAX_RECOMMENDATIONS
) -> list[dict]:
    """Persist up to `limit` fresh recommendations, best fit first.

    Skips a target that already has an unseen recommendation (so the card
    doesn't fill with duplicates across repeated scans).
    """
    # recommend_to_owner first, then by compatibility — decisions are already
    # score-ordered, so a stable sort on the flag preserves that tiebreak.
    ranked = sorted(
        (d for d in decisions if d["action"] != "skip"),
        key=lambda d: (d["recommend"], d["compat"]["score"]),
        reverse=True,
    )
    created: list[AgentRecommendation] = []
    for d in ranked:
        if len(created) >= limit:
            break
        other = d["agent"]
        if _has_unseen_rec(db, agent.id, other.id):
            continue
        rec = AgentRecommendation(
            agent_id=agent.id,
            recommended_user_id=other.user_id,
            recommended_agent_id=other.id,
            recommended_name=(other.user.name if other.user else other.name) or other.name,
            reason=d["reason"][:500],
            compatibility_score=d["compat"]["score"],
            suggested_action=d["action"],
        )
        db.add(rec)
        created.append(rec)
    if created:
        db.commit()
        for r in created:
            db.refresh(r)
    return [_rec_dict(r) for r in created]


def recommendations_for_agent(
    db: Session, agent_id: str, include_seen: bool = False, limit: int = 10
) -> list[dict]:
    q = db.query(AgentRecommendation).filter(AgentRecommendation.agent_id == agent_id)
    if not include_seen:
        q = q.filter(AgentRecommendation.seen == False)  # noqa: E712
    rows = q.order_by(AgentRecommendation.created_at.desc()).limit(limit).all()
    return [_rec_dict(r) for r in rows]


def mark_recommendation_seen(db: Session, agent_id: str, rec_id: str) -> bool:
    r = (
        db.query(AgentRecommendation)
        .filter(
            AgentRecommendation.id == rec_id,
            AgentRecommendation.agent_id == agent_id,
        )
        .first()
    )
    if not r:
        return False
    r.seen = True
    db.commit()
    return True


def mark_all_seen(db: Session, agent_id: str) -> int:
    n = (
        db.query(AgentRecommendation)
        .filter(
            AgentRecommendation.agent_id == agent_id,
            AgentRecommendation.seen == False,  # noqa: E712
        )
        .update({"seen": True}, synchronize_session=False)
    )
    db.commit()
    return n


# ── The full cycle ───────────────────────────────────────────────────────────
def run_a2a_cycle(
    db: Session,
    agent: Agent,
    *,
    do_outreach: bool = True,
    max_recommendations: int = MAX_RECOMMENDATIONS,
) -> dict:
    """Run one end-to-end A2A cycle for `agent`. Returns a summary dict."""
    logger.info("[A2A] %s starting network scan…", agent.name)
    sync_agent_profile(db, agent)

    candidates = _gather_candidates(db, agent)
    summary: dict = {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "scanned": len(candidates),
        "decisions": [],
        "reached_out": [],
        "recommendations": [],
    }

    if not candidates:
        logger.info("[A2A] %s found no new candidates to scan.", agent.name)
        log_event(logger, "a2a_cycle", agent_id=agent.id, scanned=0)
        return summary

    pool = candidates[:DECISION_POOL]
    # Log the top discoveries (mirrors the existing network_scan behavior).
    for other, compat in pool[:5]:
        log_discovery(
            db, agent.id, other.id, compat["score"], compat["reason"],
            acted_on=False, commit=False,
        )
    db.commit()

    decisions = decide_outreach(db, agent, pool)
    for d in decisions:
        logger.info(
            "[A2A]   %s → %s: %s (compat %.0f) — %s",
            agent.name, d["agent"].name, d["action"].upper(),
            d["compat"]["score"], d["reason"],
        )
    summary["decisions"] = [
        {
            "agent_id": d["agent"].id,
            "name": d["agent"].name,
            "action": d["action"],
            "recommend_to_owner": d["recommend"],
            "compatibility_score": d["compat"]["score"],
            "reason": d["reason"],
        }
        for d in decisions
    ]

    if do_outreach:
        _do_outreach(db, agent, decisions, summary)

    summary["recommendations"] = generate_recommendations(
        db, agent, decisions, max_recommendations
    )

    logger.info(
        "[A2A] %s done — scanned %d, reached out to %d, recommended %d.",
        agent.name, summary["scanned"],
        len(summary["reached_out"]), len(summary["recommendations"]),
    )
    log_event(
        logger, "a2a_cycle",
        agent_id=agent.id,
        scanned=summary["scanned"],
        reached_out=len(summary["reached_out"]),
        recommended=len(summary["recommendations"]),
    )
    return summary


def _do_outreach(
    db: Session, agent: Agent, decisions: list[dict], summary: dict
) -> None:
    """Act on the best fits: one DM + up to MAX_FOLLOWS_PER_CYCLE follows."""
    # DM — the single highest-fit candidate the agent chose to message, gated by
    # the daily initiation limit so the agent never spams the network.
    dm_choices = [
        d for d in decisions
        if d["action"] == "dm" and d["compat"]["score"] >= DM_SCORE_FLOOR
    ]
    if dm_choices and can_initiate(db, agent):
        d = dm_choices[0]
        target = d["agent"]
        interaction, _ = run_interaction(db, agent, target)
        add_memory(
            db, agent, AgentMemoryType.interaction,
            f"Reached out to {target.name} — {d['reason']} "
            f"(compat {d['compat']['score']:.0f}).",
            importance=0.6,
        )
        log_activity(
            db, agent.id, ActivityType.a2a_sent,
            f"Your agent reached out to {target.name}.",
            metadata={"interaction_id": interaction.id, "target_agent_id": target.id},
        )
        logger.info("[A2A] %s SENT intro → %s", agent.name, target.name)
        summary["reached_out"].append({
            "action": "dm",
            "agent_id": target.id,
            "name": target.name,
            "interaction_id": interaction.id,
            "compatibility_score": d["compat"]["score"],
        })

    # Follows — lightweight, capped.
    follows = 0
    for d in decisions:
        if follows >= MAX_FOLLOWS_PER_CYCLE:
            break
        if d["action"] != "follow" or d["compat"]["score"] < FOLLOW_SCORE_FLOOR:
            continue
        target = d["agent"]
        if not _follow(db, agent, target):
            continue
        upsert_connection(
            db, agent.id, target.id,
            compatibility_score=d["compat"]["score"],
            connection_type=ConnectionType.following,
            initiated_by=agent.id,
        )
        log_activity(
            db, agent.id, ActivityType.a2a_sent,
            f"Your agent followed {target.name}.",
            metadata={"following_agent_id": target.id},
        )
        logger.info("[A2A] %s FOLLOWED → %s", agent.name, target.name)
        summary["reached_out"].append({
            "action": "follow",
            "agent_id": target.id,
            "name": target.name,
            "compatibility_score": d["compat"]["score"],
        })
        follows += 1


def run_cycle_for_all(db: Session) -> int:
    """Scheduler entry — run a cycle for every agent. Returns agents processed."""
    processed = 0
    for agent in db.query(Agent).all():
        if not agent.user:
            continue
        try:
            run_a2a_cycle(db, agent)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            log_event(logger, "a2a_cycle_failed", agent_id=agent.id, error=str(exc))
    return processed
