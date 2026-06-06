"""GET /briefing — login briefing endpoint.

Called by the frontend on app open to get Jarvis's greeting, today's agenda,
and a set of pre-drafted proposed_actions.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import current_user_id
from auth import get_valid_access_token
from briefing_builder import build_briefing
from db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.get("")
async def get_briefing(
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    """
    Build and return the login briefing for the authenticated user.

    Returns:
        greeting, agenda, email_summary, tone, proposed_actions, connection_count
    """
    try:
        access_token = await get_valid_access_token(uid, db)
    except ValueError as exc:
        # User hasn't completed OAuth or token is missing — return a minimal briefing
        logger.info("No OAuth token for user %s: %s", uid, exc)
        access_token = None

    if access_token is None:
        # Graceful degradation: no calendar/email data yet
        return {
            "greeting":         "Welcome back. Connect your Google account to unlock your full briefing.",
            "agenda":           [],
            "email_summary":    "",
            "tone":             "calm",
            "proposed_actions": [],
            "connection_count": 0,
        }

    try:
        return await build_briefing(uid, access_token)
    except Exception as exc:
        logger.error("Briefing build failed for user %s: %s", uid, exc)
        raise HTTPException(status_code=500, detail="Briefing build failed.")
