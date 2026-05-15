from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User, AgentMemory, UserPersonality, ConversationSummary
from app.api.envelope import envelope


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/personality")
def personality(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    p = db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
    return envelope({
        "agent_personality": user.agent.personality_vector or {},
        "user_traits": (p.traits if p else {}) or {},
        "interests": (p.interests if p else []) or [],
        "communication_style": (p.communication_style if p else "") or "",
        "notes": (p.notes if p else "") or "",
    }, agent_id=user.agent.id)


@router.get("/timeline")
def timeline(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    mems = (
        db.query(AgentMemory)
        .filter(AgentMemory.agent_id == user.agent.id)
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
        .all()
    )
    return envelope([
        {
            "id": m.id,
            "memory_type": m.memory_type.value,
            "content": m.content,
            "importance_score": m.importance_score,
            "created_at": m.created_at.isoformat(),
        }
        for m in mems
    ], agent_id=user.agent.id)


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    summaries = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user.id)
        .order_by(ConversationSummary.created_at.desc())
        .limit(10)
        .all()
    )
    return envelope([
        {
            "id": s.id,
            "summary": s.summary,
            "message_count": s.message_count,
            "created_at": s.created_at.isoformat(),
        }
        for s in summaries
    ], agent_id=user.agent.id if user.agent else None)
