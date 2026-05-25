"""Resolve the "active" agent for a request.

A user may own multiple agents (one is_primary=True, others is_primary=False).
The frontend signals which one is active via the X-Agent-Id header. Endpoints
that care about voice/context use this resolver; endpoints that are user-level
(chat history, tool tokens) keep their existing user-scoped logic.

Resolution order:
  1. X-Agent-Id header — must be owned by the calling user.
  2. The user's primary agent (via get_primary_agent).

Returning None — and raising 404 — only happens when the user has no agents
at all, which is recoverable by the chat-route self-heal that calls
create_agent_for_user.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Agent, User
from app.services.agent_service import get_primary_agent


def resolve_active_agent(
    db: Session, user: User, agent_id: str | None
) -> Agent | None:
    """Pure function — no FastAPI deps — so tests and scheduler code can reuse it."""
    if agent_id:
        ag = (
            db.query(Agent)
            .filter(Agent.id == agent_id, Agent.user_id == user.id)
            .first()
        )
        if not ag:
            # An invalid X-Agent-Id from the client is a 403, not a silent
            # fallback — a silent fallback would mask bugs in the switcher.
            raise HTTPException(
                status_code=403, detail="Agent not owned by this user"
            )
        return ag
    return get_primary_agent(db, user.id)


def get_active_agent(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
) -> Agent:
    """FastAPI dependency — for endpoints that operate in an agent's voice."""
    ag = resolve_active_agent(db, user, x_agent_id)
    if not ag:
        raise HTTPException(status_code=404, detail="No agent for this user")
    return ag
