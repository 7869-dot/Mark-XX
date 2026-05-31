"""Private Inter-Agent Collaboration.

Two mutually-following users' agents open a CollaborationSession and exchange
*anonymized intent signals* over the a2a bus — every message passing through the
privacy_filter middleware (PII stripped) and stored as an encrypted transcript.
From the overlap an agent drafts a collaboration proposal, surfaced to each
owner as "your agent found a potential collaborator — want to connect?".

Neither user ever sees raw data about the other — only the derived, PII-free
signal and the proposal. Every cross-user action is written to privacy_audit_log.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import (
    Agent, AgentFollow, CollaborationSession, CollaborationProposal, NotificationType,
    SESSION_ACTIVE, SESSION_PROPOSED, PROPOSAL_PENDING, PROPOSAL_ACCEPTED, PROPOSAL_DECLINED,
)
from app.services import notifications, privacy_filter
from app.services import google_auth

logger = get_logger("axolot.collab")

# Don't re-run a session more often than this (keeps the bus quiet, natural).
SESSION_COOLDOWN_HOURS = 12


def _ordered(a_id: str, b_id: str) -> tuple[str, str]:
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def mutual_follow(db: Session, a_id: str, b_id: str) -> bool:
    def follows(x, y):
        return (
            db.query(AgentFollow.id)
            .filter(AgentFollow.follower_agent_id == x, AgentFollow.following_agent_id == y)
            .first()
            is not None
        )
    return follows(a_id, b_id) and follows(b_id, a_id)


def ensure_session(db: Session, agent_a: Agent, agent_b: Agent) -> CollaborationSession | None:
    """Get/create the channel — only for a mutually-following pair (opt-in)."""
    if agent_a.id == agent_b.id or not mutual_follow(db, agent_a.id, agent_b.id):
        return None
    lo, hi = _ordered(agent_a.id, agent_b.id)
    sess = (
        db.query(CollaborationSession)
        .filter(CollaborationSession.agent_a_id == lo, CollaborationSession.agent_b_id == hi)
        .first()
    )
    if not sess:
        sess = CollaborationSession(agent_a_id=lo, agent_b_id=hi, state=SESSION_ACTIVE)
        db.add(sess)
        db.commit()
        db.refresh(sess)
    return sess


def _bus_send(db: Session, sender: Agent, recipient: Agent, signal: str) -> str:
    """Privacy-filter middleware over the a2a bus: strip PII, audit, transmit.

    The transmitted content is the already-anonymized intent signal, scrubbed
    once more as a safety net. Returns the transmitted (safe) text.
    """
    names = [n for n in [(sender.user.name if sender.user else None), sender.name] if n]
    safe = privacy_filter.strip_pii(signal, names=names)
    privacy_filter.audit(
        db, sender, recipient.user_id,
        action="a2a_intent_signal",
        reason="Shared an anonymized intent signal to find a collaborator.",
        metadata={"signal": safe, "channel": "collaboration"},
        commit=False,
    )
    # Route over the existing async a2a bus (the AgentMessage queue).
    from app.services import a2a_async
    try:
        a2a_async.send_message(db, sender, recipient, f"[collab] {safe}")
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "collab_bus_send_failed", error=str(exc))
    return safe


def run_session(db: Session, session: CollaborationSession) -> list[CollaborationProposal]:
    """Exchange intent signals and, if there's overlap, draft proposals for both
    owners. Idempotent-ish: skips if a pending proposal already exists or the
    session ran within the cooldown."""
    if session.last_run_at and session.last_run_at > datetime.utcnow() - timedelta(hours=SESSION_COOLDOWN_HOURS):
        return []
    existing_pending = (
        db.query(CollaborationProposal)
        .filter(CollaborationProposal.session_id == session.id, CollaborationProposal.status == PROPOSAL_PENDING)
        .count()
    )
    if existing_pending:
        return []

    a = db.query(Agent).filter(Agent.id == session.agent_a_id).first()
    b = db.query(Agent).filter(Agent.id == session.agent_b_id).first()
    if not (a and b and a.user and b.user):
        return []

    # Each agent derives a PII-free intent from its own (private) worldview.
    signal_a = privacy_filter.derive_intent_signal(db, a)
    signal_b = privacy_filter.derive_intent_signal(db, b)

    # Exchange over the bus (middleware applied both directions).
    safe_a = _bus_send(db, a, b, signal_a)
    safe_b = _bus_send(db, b, a, signal_b)

    # Persist the encrypted transcript (never returned to a client).
    transcript = json.dumps({"a": safe_a, "b": safe_b, "at": datetime.utcnow().isoformat()})
    session.encrypted_transcript = google_auth.encrypt(transcript)
    session.last_run_at = datetime.utcnow()

    proposal_text = _negotiate(db, a, safe_a, safe_b)

    # One proposal per owner — each sees the OTHER's anonymized intent.
    p_to_a = CollaborationProposal(
        session_id=session.id, from_agent_id=b.id, to_agent_id=a.id, to_user_id=a.user_id,
        from_intent=safe_b, proposal_text=proposal_text, status=PROPOSAL_PENDING,
    )
    p_to_b = CollaborationProposal(
        session_id=session.id, from_agent_id=a.id, to_agent_id=b.id, to_user_id=b.user_id,
        from_intent=safe_a, proposal_text=proposal_text, status=PROPOSAL_PENDING,
    )
    db.add_all([p_to_a, p_to_b])
    session.state = SESSION_PROPOSED
    db.commit()

    for owner_id in (a.user_id, b.user_id):
        notifications.notify(
            db, owner_id, NotificationType.RECOMMENDATION,
            "Your agent found a potential collaborator",
            proposal_text, link="/collab",
        )
    log_event(logger, "collab_proposed", session_id=session.id)
    db.refresh(p_to_a); db.refresh(p_to_b)
    return [p_to_a, p_to_b]


def _negotiate(db: Session, drafting_agent: Agent, intent_a: str, intent_b: str) -> str:
    from app.services.gemini import generate_for_agent

    instruction = (
        "Two people on the network each shared an anonymized intent. Propose, in "
        "2 sentences, a specific reason they should connect and what they could do "
        "together. Neutral and concrete. No names.\n\n"
        f"Intent 1: {intent_a}\nIntent 2: {intent_b}"
    )
    text = (generate_for_agent(db, drafting_agent, instruction, response_format="collab_proposal") or "").strip().strip('"')
    return text or "Your goals look complementary — a quick intro could be worth both your time."


def run_for_agent(db: Session, agent: Agent) -> int:
    """Run collaboration for every mutual-follow partner of `agent` (manual trigger)."""
    partners = {
        r[0] for r in db.query(AgentFollow.following_agent_id)
        .filter(AgentFollow.follower_agent_id == agent.id).all()
    }
    proposals = 0
    for pid in partners:
        other = db.query(Agent).filter(Agent.id == pid).first()
        if not other:
            continue
        sess = ensure_session(db, agent, other)
        if sess:
            proposals += len(run_session(db, sess))
    return proposals


def collaboration_sweep(db: Session) -> int:
    """Scheduler entry — open/refresh sessions for all mutual-follow pairs."""
    edges = db.query(AgentFollow.follower_agent_id, AgentFollow.following_agent_id).all()
    edge_set = {(f, g) for f, g in edges}
    pairs = set()
    for f, g in edge_set:
        if (g, f) in edge_set:
            pairs.add(_ordered(f, g))
    total = 0
    for lo, hi in pairs:
        a = db.query(Agent).filter(Agent.id == lo).first()
        b = db.query(Agent).filter(Agent.id == hi).first()
        if not (a and b):
            continue
        sess = ensure_session(db, a, b)
        if sess:
            try:
                total += len(run_session(db, sess))
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                log_event(logger, "collab_session_failed", session_id=sess.id, error=str(exc))
    log_event(logger, "collaboration_sweep_done", proposals=total)
    return total


# ── Read / decide ────────────────────────────────────────────────────────────
def proposals_for_user(db: Session, user_id: str, status: str = PROPOSAL_PENDING) -> list[dict]:
    q = db.query(CollaborationProposal).filter(CollaborationProposal.to_user_id == user_id)
    if status:
        q = q.filter(CollaborationProposal.status == status)
    rows = q.order_by(CollaborationProposal.created_at.desc()).all()
    out = []
    for p in rows:
        other = db.query(Agent).filter(Agent.id == p.from_agent_id).first()
        out.append({
            "id": p.id,
            "from_agent": {"id": other.id, "name": other.name, "avatar_seed": other.avatar_seed} if other else None,
            "from_intent": p.from_intent,
            "proposal_text": p.proposal_text,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return out


def decide_proposal(db: Session, user_id: str, proposal_id: str, accept: bool) -> dict | None:
    p = (
        db.query(CollaborationProposal)
        .filter(CollaborationProposal.id == proposal_id, CollaborationProposal.to_user_id == user_id)
        .first()
    )
    if not p:
        return None
    p.status = PROPOSAL_ACCEPTED if accept else PROPOSAL_DECLINED
    p.decided_at = datetime.utcnow()
    db.commit()

    if accept:
        me = db.query(Agent).filter(Agent.id == p.to_agent_id).first()
        other = db.query(Agent).filter(Agent.id == p.from_agent_id).first()
        if me and other:
            try:
                from app.services.a2a_engine import run_interaction
                run_interaction(db, me, other, custom_message=(
                    "Our agents matched us as potential collaborators — opening the channel. "
                    "Here's what I'm working toward; would love to compare notes."
                ))
            except Exception as exc:  # noqa: BLE001
                log_event(logger, "collab_accept_intro_failed", error=str(exc))
            if other.user_id:
                notifications.notify(
                    db, other.user_id, NotificationType.AGENT_INTERACTION,
                    "A collaborator accepted your agent's proposal",
                    "Your agents are now connected.", link="/network",
                )
    return {"id": p.id, "status": p.status}
