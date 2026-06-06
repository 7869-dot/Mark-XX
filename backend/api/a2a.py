"""FastAPI router for all A2A (Agent-to-Agent) endpoints.

Auth model (Phase 2)
────────────────────
All user-scoped endpoints require a valid JWT in the Authorization header:
    Authorization: Bearer <jwt>

The JWT is issued by GET /auth/callback after Google OAuth login.

DEV_MODE fallback: if DEV_MODE=true in .env, the legacy X-User-Id header is
accepted as a fallback so seeded users can be tested without Google OAuth.
Set DEV_MODE=false (default) in any environment accessible from the internet.

Safety invariants upheld here
──────────────────────────────
• A user can ONLY act as the identity encoded in their own JWT.
• Contact details are NEVER returned until status == "approved".
• Private AgentCard fields do not exist — the model only stores public data.
• Approve is the ONLY transition toward contact exchange.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

import matchmaker
from auth import verify_jwt
from config import DEV_MODE
from db import get_db
from models import (
    A2AMessage, AgentCard, Briefing, ConnectionProposal, User,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Auth dependency ────────────────────────────────────────────────────────────

async def current_user_id(
    authorization: str | None = Header(None),
    x_user_id:    str | None = Header(None),
) -> str:
    """
    Resolve the calling user's ID.

    Priority:
      1. JWT in Authorization: Bearer <token>  (always accepted)
      2. X-User-Id header                      (only when DEV_MODE=true)

    Raises HTTP 401 if neither is present / valid.
    """
    if authorization and authorization.startswith("Bearer "):
        try:
            return verify_jwt(authorization[7:])
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid or expired JWT")

    if DEV_MODE and x_user_id:
        return x_user_id

    raise HTTPException(
        status_code=401,
        detail=(
            "Authentication required. Send 'Authorization: Bearer <jwt>'. "
            + ("X-User-Id accepted in DEV_MODE." if DEV_MODE else "")
        ),
    )


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AgentCardIn(BaseModel):
    display_name: str
    public_bio:   str = ""
    building:     str = ""
    looking_for:  str = ""
    can_offer:    str = ""
    tags:         list[str] = []
    is_public:    bool = True
    a2a_enabled:  bool = True


class AgentCardOut(BaseModel):
    id:           str
    user_id:      str
    display_name: str
    public_bio:   str
    building:     str
    looking_for:  str
    can_offer:    str
    tags:         list[str]
    is_public:    bool
    a2a_enabled:  bool
    updated_at:   datetime


class MessageOut(BaseModel):
    role:    str
    content: str
    turn:    int


class ProposalOut(BaseModel):
    id:                     str
    status:                 str
    match_score:            float
    match_reason:           str
    proposed_collaboration: str
    what_each_brings:       str
    confidence:             float
    partner_name:           str   # display_name of the other party
    created_at:             datetime
    transcript:             list[MessageOut]


class BriefingOut(BaseModel):
    id:             str
    summary:        str
    recommendation: str
    seen:           bool
    created_at:     datetime
    proposal:       ProposalOut


class UserOut(BaseModel):
    id:           str
    display_name: str
    created_at:   datetime


class UserIn(BaseModel):
    display_name: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, Model, id_: str, label: str = "Record"):
    obj = db.get(Model, id_)
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


def _build_proposal_out(
    proposal: ConnectionProposal,
    viewer_card_id: str,
    db: Session,
) -> ProposalOut:
    partner_id = (
        proposal.agent_b_id
        if proposal.agent_a_id == viewer_card_id
        else proposal.agent_a_id
    )
    partner_card = db.get(AgentCard, partner_id)
    partner_name = partner_card.display_name if partner_card else "Unknown"

    msgs = (
        db.query(A2AMessage)
        .filter_by(proposal_id=proposal.id)
        .order_by(A2AMessage.turn)
        .all()
    )

    return ProposalOut(
        id                     = proposal.id,
        status                 = proposal.status,
        match_score            = proposal.match_score or 0.0,
        match_reason           = proposal.match_reason or "",
        proposed_collaboration = proposal.proposed_collaboration or "",
        what_each_brings       = proposal.what_each_brings or "",
        confidence             = proposal.confidence or 0.0,
        partner_name           = partner_name,
        created_at             = proposal.created_at,
        transcript             = [
            MessageOut(role=m.role, content=m.content, turn=m.turn)
            for m in msgs
        ],
    )


# ── User endpoints (dev / seed) ────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db)):
    user = User(display_name=body.display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Agent Card endpoints ───────────────────────────────────────────────────────

@router.get("/agent-card/me", response_model=AgentCardOut)
def get_my_card(
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    card = db.query(AgentCard).filter_by(user_id=uid).first()
    if not card:
        raise HTTPException(status_code=404, detail="No agent card yet — create one with PUT /agent-card/me")
    return card


@router.put("/agent-card/me", response_model=AgentCardOut)
def upsert_my_card(
    body: AgentCardIn,
    uid:  str     = Depends(current_user_id),
    db:   Session = Depends(get_db),
):
    # Ensure user exists
    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    card = db.query(AgentCard).filter_by(user_id=uid).first()
    if card:
        card.display_name = body.display_name
        card.public_bio   = body.public_bio
        card.building     = body.building
        card.looking_for  = body.looking_for
        card.can_offer    = body.can_offer
        card.tags         = body.tags
        card.is_public    = body.is_public
        card.a2a_enabled  = body.a2a_enabled
        card.updated_at   = datetime.utcnow()
    else:
        card = AgentCard(user_id=uid, **body.model_dump())
        db.add(card)

    db.commit()
    db.refresh(card)
    return card


@router.get("/agent-card/{user_id}", response_model=AgentCardOut)
def get_public_card(user_id: str, db: Session = Depends(get_db)):
    """Return another user's public card (only if is_public=True)."""
    card = db.query(AgentCard).filter_by(user_id=user_id, is_public=True).first()
    if not card:
        raise HTTPException(status_code=404, detail="No public agent card for this user")
    return card


# ── Briefings endpoints ────────────────────────────────────────────────────────

@router.get("/briefings", response_model=list[BriefingOut])
def list_briefings(
    include_seen: bool    = False,
    uid:          str     = Depends(current_user_id),
    db:           Session = Depends(get_db),
):
    """Return briefings for the logged-in user, newest first."""
    q = db.query(Briefing).filter_by(user_id=uid)
    if not include_seen:
        q = q.filter_by(seen=False)
    briefings = q.order_by(Briefing.created_at.desc()).all()

    # Get my card id for perspective-aware partner name
    my_card = db.query(AgentCard).filter_by(user_id=uid).first()
    my_card_id = my_card.id if my_card else ""

    return [
        BriefingOut(
            id             = b.id,
            summary        = b.summary,
            recommendation = b.recommendation,
            seen           = b.seen,
            created_at     = b.created_at,
            proposal       = _build_proposal_out(
                _get_or_404(db, ConnectionProposal, b.proposal_id, "Proposal"),
                my_card_id,
                db,
            ),
        )
        for b in briefings
    ]


@router.post("/briefings/{briefing_id}/seen")
def mark_seen(
    briefing_id: str,
    uid: str     = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    b = _get_or_404(db, Briefing, briefing_id, "Briefing")
    if b.user_id != uid:
        raise HTTPException(status_code=403, detail="Not your briefing")
    b.seen = True
    db.commit()
    return {"ok": True}


@router.post("/briefings/{briefing_id}/approve")
def approve_briefing(
    briefing_id: str,
    uid: str     = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    """
    The ONLY path that moves a proposal toward contact exchange.

    When both parties approve, status → "approved" and a contact-exchange
    note is returned.  Until then, no contact details are revealed.
    """
    b = _get_or_404(db, Briefing, briefing_id, "Briefing")
    if b.user_id != uid:
        raise HTTPException(status_code=403, detail="Not your briefing")

    proposal = _get_or_404(db, ConnectionProposal, b.proposal_id, "Proposal")

    if proposal.status == "rejected":
        raise HTTPException(status_code=409, detail="Proposal already rejected")
    if proposal.status == "approved":
        return {"status": "approved", "message": "Already fully approved"}

    b.seen = True
    db.commit()

    # Determine current approval state
    my_card    = db.query(AgentCard).filter_by(user_id=uid).first()
    is_party_a = my_card and my_card.id == proposal.agent_a_id

    if proposal.status == "proposed":
        proposal.status = "approved_by_a" if is_party_a else "approved_by_b"
    elif proposal.status == "approved_by_a" and not is_party_a:
        proposal.status = "approved"
    elif proposal.status == "approved_by_b" and is_party_a:
        proposal.status = "approved"
    # else: already in this party's approved state

    proposal.updated_at = datetime.utcnow()
    db.commit()

    if proposal.status == "approved":
        # Both sides approved — in a real deployment this triggers a secure
        # contact-exchange flow (shared token, intermediary relay, etc.)
        # TODO: implement contact-exchange mechanism
        return {
            "status": "approved",
            "message": (
                "Both parties have approved! Contact exchange is now unlocked. "
                "In production, secure contact details would be shared here."
            ),
        }

    return {
        "status": proposal.status,
        "message": "Your approval is recorded. Waiting for the other party to review.",
    }


@router.post("/briefings/{briefing_id}/reject")
def reject_briefing(
    briefing_id: str,
    uid: str     = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    b = _get_or_404(db, Briefing, briefing_id, "Briefing")
    if b.user_id != uid:
        raise HTTPException(status_code=403, detail="Not your briefing")

    proposal = _get_or_404(db, ConnectionProposal, b.proposal_id, "Proposal")
    proposal.status     = "rejected"
    proposal.updated_at = datetime.utcnow()
    b.seen = True
    db.commit()
    return {"status": "rejected"}


# ── Admin / Dev endpoints ──────────────────────────────────────────────────────

@router.post("/admin/run-matchmaking")
async def admin_run_all():
    """Trigger a full matchmaking cycle for all users (dev/testing)."""
    results = await matchmaker.run_all()
    total = sum(len(v) for v in results.values())
    return {"proposals_created": total, "by_user": results}


@router.post("/admin/run-matchmaking/{user_id}")
async def admin_run_for_user(user_id: str):
    """Trigger a matchmaking cycle for a specific user (dev/testing)."""
    pids = await matchmaker.run_cycle(user_id)
    return {"proposals_created": len(pids), "proposal_ids": pids}


@router.get("/admin/proposals")
def admin_list_proposals(db: Session = Depends(get_db)):
    """List all proposals (dev/testing)."""
    proposals = db.query(ConnectionProposal).order_by(
        ConnectionProposal.created_at.desc()
    ).all()
    return [
        {
            "id":            p.id,
            "agent_a":       (db.get(AgentCard, p.agent_a_id) or AgentCard(display_name="?")).display_name,
            "agent_b":       (db.get(AgentCard, p.agent_b_id) or AgentCard(display_name="?")).display_name,
            "status":        p.status,
            "confidence":    p.confidence,
            "idea":          p.proposed_collaboration,
            "created_at":    p.created_at,
        }
        for p in proposals
    ]
