"""Email Agent — composes a professional email draft for user approval.

Uses Gemini's response_schema (native structured output) instead of tool forcing.
This is simpler than function calling for a single-shot structured response.

The draft is returned to the orchestrator; no email is sent until the user
explicitly approves it via POST /confirm-email.
"""
from __future__ import annotations

import json
from typing import Callable

from google import genai
from google.genai import types
from pydantic import BaseModel

from config import GOOGLE_API_KEY, GEMINI_MODEL

_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


# ── Structured output schema ───────────────────────────────────────────────────

class _EmailDraft(BaseModel):
    to:      str
    subject: str
    body:    str


_SYSTEM = (
    "You are the Email Agent, an expert email composer. "
    "You write clear, professional emails based on provided content.\n\n"
    "Rules:\n"
    "- Subject lines should be specific and informative.\n"
    "- Body should be well-structured: greeting, content, sign-off.\n"
    "- Keep it concise but complete.\n"
    "- Return ONLY valid JSON matching the required schema."
)

_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM,
    response_mime_type="application/json",
    response_schema=_EmailDraft,
)


# ── Public API ─────────────────────────────────────────────────────────────────

def run(task: str, on_step: Callable[[str], None] | None = None) -> dict:
    """Compose an email draft. Returns {to, subject, body}."""
    if on_step:
        on_step("Composing email draft…")

    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=task,
        config=_CONFIG,
    )

    try:
        data = json.loads(response.text)
        return {
            "to":      data.get("to", ""),
            "subject": data.get("subject", "Draft"),
            "body":    data.get("body", ""),
        }
    except Exception:
        # Fallback: return raw text if JSON parsing fails
        return {"to": "", "subject": "Draft", "body": response.text, "_fallback": True}
