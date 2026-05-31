"""User-scoped endpoints — display name + the onboarding gate.

Distinct from /agent/* (the agent's identity). These touch the human's User row.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "onboarding_complete": bool(user.onboarding_complete),
    }


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    """The human behind the agent — includes onboarding_complete for routing."""
    return envelope(_user_dict(user), agent_id=user.agent.id if user.agent else None)


class UserUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


@router.put("/me")
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the user's display name (captured in onboarding step 1)."""
    user.name = payload.name.strip()[:80]
    db.commit()
    return envelope(_user_dict(user), agent_id=user.agent.id if user.agent else None)


class MemoryUpdate(BaseModel):
    key: str = Field(..., min_length=1, max_length=40)
    value: str = Field(..., min_length=1, max_length=500)


@router.post("/me/memory")
def update_memory(
    payload: MemoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the user's PersonalityMatrix / TopicInterestProfile from any client
    (used by the MCP agent_memory_update tool).

    key:
      topic|interest        -> add to the TopicInterestProfile
      communication_style   -> set the speech style
      goal                  -> append to the user's goals
      anything else         -> appended to personality notes
    """
    from app.models import UserPersonality
    from app.services import agent_web

    key = payload.key.strip().lower()
    value = payload.value.strip()
    applied = key

    if key in ("topic", "interest"):
        agent_web.upsert_topic(db, user.id, value, source="manual", delta=1.0)
        applied = "topic"
    elif key == "goal":
        user.goals = list(user.goals or []) + [value]
        db.commit()
    else:
        up = db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
        if not up:
            up = UserPersonality(user_id=user.id, interests=[], traits={})
            db.add(up)
        if key == "communication_style":
            up.communication_style = value
        else:
            up.notes = ((up.notes or "") + f"\n[{key}] {value}").strip()
            applied = "notes"
        db.commit()

    return envelope({"applied": applied, "key": key}, agent_id=user.agent.id if user.agent else None)


@router.put("/me/onboarding-complete")
def complete_onboarding(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Mark onboarding finished (called from the 'See your feed →' button).
    Idempotent — safe to call more than once."""
    user.onboarding_complete = True
    db.commit()
    return envelope(
        {"onboarding_complete": True},
        agent_id=user.agent.id if user.agent else None,
    )
