"""Sprint 6 API — private inter-agent collaboration (proposals inbox)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import User
from app.services import agent_collab

router = APIRouter(prefix="/collab", tags=["collab"])


@router.get("/proposals")
def proposals(
    status: str = "pending",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Collaboration Inbox — proposals surfaced to the caller."""
    return envelope({"items": agent_collab.proposals_for_user(db, user.id, status=status)})


@router.post("/proposals/{proposal_id}/accept")
def accept(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    res = agent_collab.decide_proposal(db, user.id, proposal_id, accept=True)
    if not res:
        raise HTTPException(status_code=404, detail="proposal not found")
    return envelope(res)


@router.post("/proposals/{proposal_id}/decline")
def decline(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    res = agent_collab.decide_proposal(db, user.id, proposal_id, accept=False)
    if not res:
        raise HTTPException(status_code=404, detail="proposal not found")
    return envelope(res)


@router.post("/run")
@limiter.limit("6/minute")
def run(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Manually run collaboration for the caller's agent (dev/testing)."""
    if not user.agent:
        raise HTTPException(status_code=400, detail="no_agent")
    n = agent_collab.run_for_agent(db, user.agent)
    return envelope({"proposals_created": n})
