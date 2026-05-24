"""New-user onboarding completion.

The 3-step onboarding flow (name your agent → connect tools → meet the
network) runs entirely against existing endpoints — PUT /agent/me, the
/integrations/* connect routes and /social/*. This router only owns the
single piece of durable state that gates the flow: users.onboarding_complete.

The flag is also surfaced on GET /agent/me so the SPA can route a returning
user straight past onboarding without an extra round-trip.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/complete")
def complete(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mark onboarding finished. Idempotent — safe to call more than once."""
    user.onboarding_complete = True
    db.commit()
    return envelope(
        {"onboarding_complete": True},
        agent_id=user.agent.id if user.agent else None,
    )
