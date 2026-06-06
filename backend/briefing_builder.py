"""Login briefing builder — runs when a user opens the app.

Chief-of-staff behaviour: synthesises calendar + inbox + connections into a
Jarvis-style greeting and pre-populates proposed_actions ready for approval.

Steps
─────
1. Fetch today's schedule (Calendar API)
2. Fetch recent unread emails (Gmail API)
3. Load unseen connection briefings (DB)
4. Call Gemini to produce a structured briefing (greeting + agenda + email_summary)
5. Pre-draft replies for the top-3 important emails → ProposedAction rows
6. Create ProposedAction(connection_approval) rows for unseen briefings

All DB writes use a fresh SessionLocal(); access_token is never persisted.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from google import genai
from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.connection_agent import get_unseen_briefings
from config import GOOGLE_API_KEY, GEMINI_MODEL
from db import SessionLocal
from models import ProposedAction
from tools import gmail_tools, calendar_tools

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


# ── Structured briefing from Gemini ───────────────────────────────────────────

class _BriefingOutput(BaseModel):
    greeting:      str
    agenda:        list[dict]   # [{time, title, note?}]
    email_summary: str
    tone:          str          # "calm" | "busy" | "hectic"


async def build_briefing(user_id: str, access_token: str) -> dict:
    """
    Build the login briefing for user_id.

    Returns:
        {
            greeting:          str,
            agenda:            [{time, title, note?}],
            email_summary:     str,
            tone:              str,
            proposed_actions:  [{id, type, payload, rationale, created_at}],
            connection_count:  int,
        }
    """
    # 1. Fetch data (may fail gracefully if scopes not granted yet)
    schedule: list[dict] = []
    emails:   list[dict] = []
    try:
        schedule = calendar_tools.get_today_schedule(access_token)
    except Exception as exc:
        logger.warning("Calendar fetch failed for user %s: %s", user_id, exc)

    try:
        emails = gmail_tools.list_recent_emails(access_token, max_results=20, query="is:unread")
    except Exception as exc:
        logger.warning("Gmail fetch failed for user %s: %s", user_id, exc)

    # 2. Unseen connections (DB only, no API call needed)
    unseen_connections = get_unseen_briefings(user_id)

    # 3. Ask Gemini to synthesise the briefing
    now_str = datetime.utcnow().strftime("%A, %d %B %Y %H:%M UTC")
    prompt = (
        f"Today is {now_str}.\n\n"
        f"CALENDAR ({len(schedule)} events):\n{json.dumps(schedule, indent=2)}\n\n"
        f"UNREAD EMAILS ({len(emails)} unread):\n{json.dumps(emails, indent=2)}\n\n"
        f"CONNECTION MATCHES (unseen): {len(unseen_connections)}\n\n"
        "Produce a Jarvis-style morning briefing:\n"
        "• greeting: warm, personal, mention the day's shape (calm/busy/hectic)\n"
        "• agenda: list of {time, title, note?} for today's events\n"
        "• email_summary: 1-2 sentences covering the most important unread emails\n"
        "• tone: one of 'calm' | 'busy' | 'hectic'\n"
        "Return ONLY valid JSON matching the schema."
    )

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are Jarvis, an anticipatory chief-of-staff AI. "
            "Be concise, warm, and proactive. Surface what matters; skip the noise."
        ),
        response_mime_type="application/json",
        response_schema=_BriefingOutput,
    )

    briefing_data: dict = {
        "greeting": "Good morning. Here's your day.",
        "agenda": [],
        "email_summary": "",
        "tone": "calm",
    }
    try:
        response = await _get_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        briefing_data = json.loads(response.text)
    except Exception as exc:
        logger.warning("Briefing Gemini call failed: %s", exc)

    # 4. Create proposed_actions and return their IDs
    proposed: list[dict] = []

    db = SessionLocal()
    try:
        # Pre-draft replies for top-3 important emails
        if emails:
            top_emails = emails[:3]
            for em in top_emails:
                draft = await _draft_reply(em, access_token)
                if draft:
                    action = _save_proposed_action(
                        db, user_id,
                        type="email_reply",
                        payload={
                            "to":             em.get("from", ""),
                            "subject":        f"Re: {em.get('subject', '')}",
                            "body":           draft,
                            "in_reply_to_id": em.get("id", ""),
                        },
                        rationale=f"Unread email from {em.get('from', 'unknown')} — suggested reply",
                    )
                    proposed.append(action)

        # Connection approvals for unseen briefings
        for conn in unseen_connections:
            # Avoid duplicates
            existing = (
                db.query(ProposedAction)
                .filter_by(user_id=user_id, type="connection_approval", status="pending")
                .all()
            )
            existing_ids = {a.payload.get("briefing_id") for a in existing if a.payload}
            if conn["briefing_id"] in existing_ids:
                continue
            action = _save_proposed_action(
                db, user_id,
                type="connection_approval",
                payload={
                    "briefing_id":  conn["briefing_id"],
                    "proposal_id":  conn["proposal_id"],
                    "partner_name": conn["partner_name"],
                    "summary":      conn["summary"],
                },
                rationale=f"New connection match: {conn['partner_name']}",
            )
            proposed.append(action)

        db.commit()
    finally:
        db.close()

    return {
        **briefing_data,
        "proposed_actions": proposed,
        "connection_count": len(unseen_connections),
    }


async def _draft_reply(email: dict, access_token: str) -> str:
    """Use Gemini to draft a brief reply to an email. Returns empty string on failure."""
    try:
        full = gmail_tools.read_email(access_token, email["id"])
        prompt = (
            f"Email from: {full.get('from', '')}\n"
            f"Subject: {full.get('subject', '')}\n"
            f"Body:\n{full.get('body', '')[:2000]}\n\n"
            "Write a concise, professional reply. Just the body text, no greeting needed."
        )
        response = await _get_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as exc:
        logger.warning("Reply draft failed for email %s: %s", email.get("id"), exc)
        return ""


def _save_proposed_action(
    db: Session,
    user_id: str,
    type: str,
    payload: dict,
    rationale: str = "",
) -> dict:
    """Persist a ProposedAction row and return a summary dict."""
    action = ProposedAction(
        user_id=user_id,
        type=type,
        payload=payload,
        rationale=rationale,
        status="pending",
    )
    db.add(action)
    db.flush()  # get the generated id without committing
    return {
        "id":         action.id,
        "type":       action.type,
        "payload":    action.payload,
        "rationale":  action.rationale,
        "created_at": action.created_at.isoformat() if action.created_at else "",
    }
