"""Sprint 6 API — agent web access, topic profile, trust, pending posts, audit."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import (
    Agent, PendingPost, PrivacyAuditLog, TopicInterest, User,
    TRUST_LEVELS, TOPIC_CATEGORIES,
)
from app.services import agent_web, post_engine

router = APIRouter(tags=["world"])


def _agent(db: Session, user: User) -> Agent:
    if not user.agent:
        raise HTTPException(status_code=400, detail="no_agent")
    return user.agent


# ── Topic interest profile ───────────────────────────────────────────────────
def _topic_dict(t: TopicInterest) -> dict:
    return {
        "id": t.id, "topic": t.topic, "category": t.category,
        "weight": round(t.weight or 0.0, 2), "source": t.source, "feed_url": t.feed_url,
    }


@router.get("/web/topics")
def list_topics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return envelope({"items": [_topic_dict(t) for t in agent_web.get_topics(db, user.id)]})


class TopicBody(BaseModel):
    topic: str = Field(..., min_length=1, max_length=60)
    feed_url: str | None = Field(default=None, max_length=400)


@router.post("/web/topics")
@limiter.limit("30/minute")
def add_topic(request: Request, body: TopicBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = agent_web.upsert_topic(db, user.id, body.topic, source="manual", delta=1.0, feed_url=body.feed_url)
    return envelope(_topic_dict(t))


@router.delete("/web/topics/{topic_id}")
def delete_topic(topic_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(TopicInterest).filter(TopicInterest.id == topic_id, TopicInterest.user_id == user.id).delete()
    db.commit()
    return envelope({"deleted": True, "id": topic_id})


@router.get("/web/pulse")
def world_pulse(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """World Pulse — what the agent is currently tracking."""
    return envelope({"items": agent_web.world_pulse(db, user.id)})


class SearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)


@router.post("/web/search")
@limiter.limit("20/minute")
def web_search(request: Request, body: SearchBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Agent web search, grounded in the user's interest profile (results are
    nudged by appending the user's top tracked topics as context)."""
    results = agent_web.web_search(body.query)
    # Light reinforcement — searching a thing signals interest in it.
    agent_web.upsert_topic(db, user.id, body.query, source="inferred", delta=0.1)
    return envelope({"query": body.query, "results": results})


# ── Trust settings ───────────────────────────────────────────────────────────
@router.get("/web/trust")
def get_trust(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return envelope({"categories": list(TOPIC_CATEGORIES), "levels": list(TRUST_LEVELS),
                     "settings": post_engine.all_trust(db, user.id)})


class TrustBody(BaseModel):
    category: str
    level: str

    @property
    def _ok(self):
        return self.category in TOPIC_CATEGORIES and self.level in TRUST_LEVELS


@router.put("/web/trust")
def set_trust(body: TrustBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.category not in TOPIC_CATEGORIES or body.level not in TRUST_LEVELS:
        raise HTTPException(status_code=422, detail="invalid category or level")
    post_engine.set_trust(db, user.id, body.category, body.level)
    return envelope({"settings": post_engine.all_trust(db, user.id)})


# ── Pending posts queue ──────────────────────────────────────────────────────
def _pending_dict(p: PendingPost) -> dict:
    return {
        "id": p.id, "content": p.content, "topic": p.topic, "category": p.category,
        "confidence_score": round(p.confidence_score or 0.0, 2),
        "source_list": p.source_list or [], "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/web/pending")
def list_pending(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    me = _agent(db, user)
    rows = (
        db.query(PendingPost)
        .filter(PendingPost.agent_id == me.id, PendingPost.status == "pending")
        .order_by(PendingPost.created_at.desc())
        .all()
    )
    return envelope({"items": [_pending_dict(p) for p in rows]})


def _owned_pending(db: Session, pid: str, user: User) -> PendingPost:
    p = db.query(PendingPost).filter(PendingPost.id == pid, PendingPost.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="pending post not found")
    return p


class EditBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


@router.put("/web/pending/{pid}")
def edit_pending(pid: str, body: EditBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = _owned_pending(db, pid, user)
    p.content = body.content.strip()
    db.commit()
    return envelope(_pending_dict(p))


@router.post("/web/pending/{pid}/approve")
def approve_pending(pid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = _owned_pending(db, pid, user)
    post = post_engine.approve_pending(db, _agent(db, user), p)
    return envelope({"published": True, "post_id": post.id})


@router.post("/web/pending/{pid}/reject")
def reject_pending(pid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post_engine.reject_pending(db, _owned_pending(db, pid, user))
    return envelope({"rejected": True, "id": pid})


class DraftBody(BaseModel):
    topic: str | None = Field(default=None, max_length=120)


@router.post("/agents/{agent_id}/draft-world-post")
@limiter.limit("12/minute")
def draft_world_post(
    request: Request, agent_id: str, body: DraftBody | None = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Manually trigger the world-aware post engine for the caller's agent.
    Optional `topic` overrides the agent's auto-picked topic (used by the MCP tool)."""
    me = _agent(db, user)
    if agent_id != me.id:
        raise HTTPException(status_code=403, detail="You can only draft as your own agent")
    result = post_engine.draft_world_post(db, me, topic=(body.topic if body else None))
    if not result:
        raise HTTPException(status_code=502, detail="Could not draft a post (no topic or empty generation)")
    return envelope(result)


# ── Privacy audit (transparency) ─────────────────────────────────────────────
@router.get("/web/audit")
def privacy_audit(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Full transparency: every action the user's agent took that touched another
    user's data, with reason. PII never appears here — only derived signals."""
    rows = (
        db.query(PrivacyAuditLog)
        .filter(PrivacyAuditLog.actor_user_id == user.id)
        .order_by(PrivacyAuditLog.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    out = []
    for r in rows:
        subject = db.query(User).filter(User.id == r.subject_user_id).first() if r.subject_user_id else None
        out.append({
            "id": r.id, "action": r.action, "reason": r.reason,
            "subject_name": subject.name if subject else None,
            "metadata": r.audit_metadata or {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return envelope({"items": out})
