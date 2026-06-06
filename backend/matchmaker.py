"""Matchmaking pipeline — runs as a background job or on-demand via admin endpoint.

Gemini migration notes
──────────────────────
• judge_match() and run_negotiation() are now async (async Gemini client).
• run_cycle() is now fully async — no run_in_executor needed for LLM calls.
• DB operations (SQLAlchemy sync) are short and run on the same event loop;
  acceptable for SQLite dev setup.
  TODO: switch to async SQLAlchemy (asyncpg + aiosqlite) for production.

Pipeline per user
─────────────────
  1. Discover  — other users' public, a2a-enabled AgentCards
  2. Filter    — drop pairs in cooldown (existing recent proposal)
  3. Rank      — bag-of-words cosine similarity, keep top N
  4. Judge     — async LLM scores each pair 0–1; drop below threshold
  5. Negotiate — async bounded A2A exchange → structured verdict
  6. Propose   — write ConnectionProposal + Briefings for both users

Safety: no private data ever leaves this module; only AgentCard public fields
are passed to LLM calls.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from agents.a2a_agent import judge_match, run_negotiation
from config import A2A_COOLDOWN_DAYS, A2A_MATCH_THRESHOLD
from db import SessionLocal
from embeddings import rank_candidates
from models import A2AMessage, AgentCard, Briefing, ConnectionProposal, User

logger = logging.getLogger(__name__)

_DISCOVER_LIMIT = 20
_JUDGE_LIMIT    = 8


def _card_to_dict(card: AgentCard) -> dict:
    """Extract ONLY public fields — safe to pass to LLM calls."""
    return {
        "id":           card.id,
        "user_id":      card.user_id,
        "display_name": card.display_name,
        "public_bio":   card.public_bio  or "",
        "building":     card.building    or "",
        "looking_for":  card.looking_for or "",
        "can_offer":    card.can_offer   or "",
        "tags":         card.tags        or [],
    }


def _in_cooldown(db: Session, card_a_id: str, card_b_id: str) -> bool:
    cutoff = datetime.utcnow() - timedelta(days=A2A_COOLDOWN_DAYS)
    return (
        db.query(ConnectionProposal)
        .filter(
            or_(
                and_(
                    ConnectionProposal.agent_a_id == card_a_id,
                    ConnectionProposal.agent_b_id == card_b_id,
                ),
                and_(
                    ConnectionProposal.agent_a_id == card_b_id,
                    ConnectionProposal.agent_b_id == card_a_id,
                ),
            ),
            ConnectionProposal.status.notin_(["rejected", "expired"]),
            ConnectionProposal.created_at >= cutoff,
        )
        .first()
    ) is not None


def _write_proposal_and_briefings(
    db: Session,
    card_a: AgentCard,
    card_b: AgentCard,
    match_score: float,
    match_reason: str,
    verdict: dict,
    transcript: list[dict],
) -> str:
    now = datetime.utcnow()

    proposal = ConnectionProposal(
        agent_a_id             = card_a.id,
        agent_b_id             = card_b.id,
        status                 = "proposed",
        match_score            = match_score,
        match_reason           = match_reason,
        proposed_collaboration = verdict.get("idea", ""),
        what_each_brings       = verdict.get("what_each_brings", ""),
        confidence             = verdict.get("confidence", 0.0),
        created_at             = now,
        updated_at             = now,
    )
    db.add(proposal)
    db.flush()

    for msg in transcript:
        from_id = card_a.id if msg["role"] == "agent_a" else card_b.id
        db.add(A2AMessage(
            proposal_id   = proposal.id,
            from_agent_id = from_id,
            role          = msg["role"],
            content       = msg["content"],
            turn          = msg["turn"],
        ))

    confidence_pct = f"{verdict.get('confidence', 0.0):.0%}"
    idea           = verdict.get("idea", "")
    brings         = verdict.get("what_each_brings", "")

    for viewer_card, partner_card in [(card_a, card_b), (card_b, card_a)]:
        viewer_user = db.get(User, viewer_card.user_id)
        viewer_name = viewer_user.display_name if viewer_user else "You"  # noqa: F841

        summary = (
            f"While you were away, your agent discovered **{partner_card.display_name}** "
            f"as a potential collaborator.\n\n"
            f"They are building: {partner_card.building}\n"
            f"They are looking for: {partner_card.looking_for}\n\n"
            f"Your agents negotiated and reached the following idea:\n{idea}"
        )
        recommendation = (
            f"Confidence: {confidence_pct}\n\n"
            f"What each side brings:\n{brings}\n\n"
            f"Match reason: {match_reason}\n\n"
            + (
                "Your agent recommends connecting — the overlap looks genuine."
                if verdict.get("collaborate") and verdict.get("confidence", 0) >= 0.65
                else "Explore cautiously — there is some overlap but it may not be deep."
                if verdict.get("collaborate")
                else "Your agent found the fit too weak to recommend."
            )
        )

        db.add(Briefing(
            user_id        = viewer_card.user_id,
            proposal_id    = proposal.id,
            summary        = summary,
            recommendation = recommendation,
            seen           = False,
        ))

    db.commit()
    logger.info(
        "Proposal %s created (%s <-> %s)",
        proposal.id, card_a.display_name, card_b.display_name,
    )
    return proposal.id


# ── Async cycle ────────────────────────────────────────────────────────────────

async def run_cycle(user_id: str) -> list[str]:
    """
    Full matchmaking pipeline for one user — fully async.
    judge_match() and run_negotiation() use the async Gemini client directly.
    DB operations are synchronous SQLAlchemy (acceptable for SQLite dev setup).
    """
    db = SessionLocal()
    try:
        # 1. My card
        my_card = db.query(AgentCard).filter_by(
            user_id=user_id, is_public=True, a2a_enabled=True
        ).first()
        if not my_card:
            logger.debug("User %s has no public/enabled agent card — skipping", user_id)
            return []

        # 2. Discover candidates
        candidates: list[AgentCard] = (
            db.query(AgentCard)
            .filter(
                AgentCard.user_id != user_id,
                AgentCard.is_public == True,   # noqa: E712
            )
            .limit(_DISCOVER_LIMIT)
            .all()
        )
        if not candidates:
            return []

        # 3. Cooldown filter
        fresh = [c for c in candidates if not _in_cooldown(db, my_card.id, c.id)]
        if not fresh:
            logger.debug("All candidates in cooldown for user %s", user_id)
            return []

        # 4. Rank by text similarity
        ranked = rank_candidates(my_card, fresh)[:_JUDGE_LIMIT]

        # 5. Async LLM judge
        my_dict = _card_to_dict(my_card)
        qualified: list[tuple[AgentCard, float, str]] = []
        for candidate in ranked:
            cand_dict = _card_to_dict(candidate)
            score, reason = await judge_match(my_dict, cand_dict)
            logger.debug(
                "Judge: %s <-> %s = %.2f (%s)",
                my_card.display_name, candidate.display_name, score, reason,
            )
            if score >= A2A_MATCH_THRESHOLD:
                qualified.append((candidate, score, reason))

        if not qualified:
            logger.info("No qualifying matches for user %s", user_id)
            return []

        # 6. Async negotiate and propose
        proposal_ids: list[str] = []
        for candidate, score, reason in qualified:
            try:
                logger.info(
                    "Negotiating: %s <-> %s (score=%.2f)",
                    my_card.display_name, candidate.display_name, score,
                )
                cand_dict = _card_to_dict(candidate)
                verdict = await run_negotiation(my_dict, cand_dict)
                transcript = verdict.pop("transcript", [])

                if verdict.get("collaborate", False):
                    pid = _write_proposal_and_briefings(
                        db, my_card, candidate, score, reason, verdict, transcript
                    )
                    proposal_ids.append(pid)
                else:
                    logger.info(
                        "Negotiation concluded: no collaboration (%s <-> %s)",
                        my_card.display_name, candidate.display_name,
                    )
            except Exception:
                logger.exception(
                    "Error negotiating %s <-> %s", my_card.id, candidate.id
                )

        return proposal_ids
    finally:
        db.close()


async def run_all() -> dict[str, list[str]]:
    """Run matchmaking for every user. Called by the APScheduler job."""
    db = SessionLocal()
    try:
        user_ids = [u.id for u in db.query(User).all()]
    finally:
        db.close()

    results: dict[str, list[str]] = {}
    for uid in user_ids:
        try:
            pids = await run_cycle(uid)
            if pids:
                results[uid] = pids
        except Exception:
            logger.exception("run_all: error processing user %s", uid)
    return results
