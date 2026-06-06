"""Connection Agent — thin wrapper exposing the matchmaker pipeline as a delegate tool.

Design
──────
• run() calls matchmaker.run_cycle(user_id) on demand (not just on the scheduler).
• Also surfaces existing unseen briefings so the chief can include them in briefings.
• Async: calls async matchmaker directly, no executor needed.
"""
from __future__ import annotations

import logging

from db import SessionLocal
from models import AgentCard, Briefing, ConnectionProposal

logger = logging.getLogger(__name__)


async def run(user_id: str, on_step=None) -> str:
    """
    Trigger the matchmaker pipeline for user_id and return a connection summary.

    Returns a plain-text summary suitable for inclusion in a Jarvis briefing.
    """
    import matchmaker  # late import to avoid circular

    if on_step:
        on_step("Connection Agent: scanning for new matches…")

    proposal_ids: list[str] = []
    try:
        proposal_ids = await matchmaker.run_cycle(user_id)
    except Exception as exc:
        logger.warning("Matchmaker cycle failed for user %s: %s", user_id, exc)

    db = SessionLocal()
    try:
        unseen = (
            db.query(Briefing)
            .filter_by(user_id=user_id, seen=False)
            .order_by(Briefing.created_at.desc())
            .limit(5)
            .all()
        )
        lines = []
        if proposal_ids:
            lines.append(f"Found {len(proposal_ids)} new connection proposal(s) this cycle.")
        if unseen:
            lines.append(f"You have {len(unseen)} unseen connection briefing(s) awaiting review.")
            for b in unseen:
                lines.append(f"  • {b.summary[:120]}")
        if not lines:
            lines.append("No new connection matches this cycle.")
        return "\n".join(lines)
    finally:
        db.close()


def get_unseen_briefings(user_id: str) -> list[dict]:
    """Return unseen connection briefings with proposal details. Sync helper."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Briefing)
            .filter_by(user_id=user_id, seen=False)
            .order_by(Briefing.created_at.desc())
            .limit(10)
            .all()
        )
        results = []
        for b in rows:
            prop = db.query(ConnectionProposal).filter_by(id=b.proposal_id).first()
            # Resolve partner name
            partner_name = ""
            if prop:
                my_card = db.query(AgentCard).filter_by(user_id=user_id).first()
                my_card_id = my_card.id if my_card else None
                partner_card_id = prop.agent_b_id if prop.agent_a_id == my_card_id else prop.agent_a_id
                partner_card = db.query(AgentCard).filter_by(id=partner_card_id).first()
                partner_name = partner_card.display_name if partner_card else ""
            results.append({
                "briefing_id":  b.id,
                "proposal_id":  b.proposal_id,
                "summary":      b.summary,
                "recommendation": b.recommendation,
                "partner_name": partner_name,
                "created_at":   b.created_at.isoformat() if b.created_at else "",
            })
        return results
    finally:
        db.close()
