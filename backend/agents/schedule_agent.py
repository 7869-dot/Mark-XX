"""Schedule & Email Agent — reads Gmail/Calendar and proposes actions for approval.

Design
──────
• Tools that fetch data (list_recent_emails, read_email, get_today_schedule) call
  the APIs and return results directly.
• Action tools (draft_email_reply, propose_calendar_event) do NOT send or create —
  they return a structured proposed_action dict that the orchestrator persists to DB
  after the agent run completes.
• The access_token is closed over inside dispatch(); it is never passed to the LLM.
• Called synchronously from orchestrator via run_in_executor.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL
from tools import gmail_tools, calendar_tools

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


# ── Tool declarations ──────────────────────────────────────────────────────────

_TOOLS_DECL = [
    types.FunctionDeclaration(
        name="list_recent_emails",
        description="List recent emails from the user's Gmail inbox.",
        parameters={
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Max emails to return (default 10)"},
                "query":       {"type": "string",  "description": "Gmail search query (default: is:unread)"},
            },
        },
    ),
    types.FunctionDeclaration(
        name="read_email",
        description="Read the full content of a specific email by its ID.",
        parameters={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Gmail message ID"},
            },
            "required": ["message_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_today_schedule",
        description="Get the user's calendar events for today.",
        parameters={"type": "object", "properties": {}},
    ),
    types.FunctionDeclaration(
        name="draft_email_reply",
        description=(
            "Propose an email reply for user approval. "
            "This does NOT send anything — it queues a proposed_action (type: email_reply) "
            "that the user must approve before any email is sent."
        ),
        parameters={
            "type": "object",
            "properties": {
                "to":              {"type": "string", "description": "Recipient email address"},
                "subject":         {"type": "string", "description": "Email subject line"},
                "body":            {"type": "string", "description": "Email body text"},
                "in_reply_to_id":  {"type": "string", "description": "Gmail message ID being replied to (optional)"},
                "rationale":       {"type": "string", "description": "Why this reply is being proposed"},
            },
            "required": ["to", "subject", "body"],
        },
    ),
    types.FunctionDeclaration(
        name="propose_calendar_event",
        description=(
            "Propose a new calendar event for user approval. "
            "This does NOT create anything — it queues a proposed_action (type: calendar_event) "
            "that the user must approve before the event is created."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title":       {"type": "string", "description": "Event title"},
                "start":       {"type": "string", "description": "Start time in ISO 8601 (UTC)"},
                "end":         {"type": "string", "description": "End time in ISO 8601 (UTC)"},
                "description": {"type": "string", "description": "Event description"},
                "attendees":   {"type": "array",  "items": {"type": "string"}, "description": "Attendee emails"},
                "rationale":   {"type": "string", "description": "Why this event is being proposed"},
            },
            "required": ["title", "start", "end"],
        },
    ),
]

_SYSTEM = (
    "You are the Schedule & Email Agent, Jarvis's sub-agent for inbox and calendar.\n\n"
    "Your job:\n"
    "1. Use list_recent_emails / read_email to understand what's in the inbox.\n"
    "2. Use get_today_schedule to understand the day.\n"
    "3. For emails that need a reply, use draft_email_reply to propose a draft.\n"
    "4. For scheduling gaps or meeting requests, use propose_calendar_event.\n"
    "5. Return a concise briefing: what's important, what needs action.\n\n"
    "CRITICAL: draft_email_reply and propose_calendar_event do NOT send or create — "
    "they only queue proposals for the user to approve. Always use them when a reply "
    "or event would be helpful, rather than just describing what could be done.\n\n"
    "Tone: direct, prioritised. Lead with the most time-sensitive items."
)

_MAX_ITER = 15


# ── Public API ─────────────────────────────────────────────────────────────────

def run(
    task: str,
    access_token: str,
    on_step: Callable[[str], None] | None = None,
) -> dict:
    """
    Run the schedule/email agent.

    Returns:
        {
            "summary":          str,              # Jarvis-style briefing text
            "proposed_actions": list[dict],       # [{type, payload, rationale}]
        }
    """
    proposed_actions: list[dict] = []

    def dispatch(name: str, args: dict) -> str:
        if name == "list_recent_emails":
            emails = gmail_tools.list_recent_emails(
                access_token,
                max_results=args.get("max_results", 10),
                query=args.get("query", "is:unread"),
            )
            return json.dumps(emails)

        if name == "read_email":
            email = gmail_tools.read_email(access_token, args["message_id"])
            return json.dumps(email)

        if name == "get_today_schedule":
            events = calendar_tools.get_today_schedule(access_token)
            return json.dumps(events)

        if name == "draft_email_reply":
            proposed_actions.append({
                "type":      "email_reply",
                "payload":   {
                    "to":             args.get("to", ""),
                    "subject":        args.get("subject", ""),
                    "body":           args.get("body", ""),
                    "in_reply_to_id": args.get("in_reply_to_id", ""),
                },
                "rationale": args.get("rationale", ""),
            })
            return "Draft queued for user approval."

        if name == "propose_calendar_event":
            proposed_actions.append({
                "type":      "calendar_event",
                "payload":   {
                    "title":       args.get("title", ""),
                    "start":       args.get("start", ""),
                    "end":         args.get("end", ""),
                    "description": args.get("description", ""),
                    "attendees":   args.get("attendees", []),
                },
                "rationale": args.get("rationale", ""),
            })
            return "Calendar event proposal queued for user approval."

        return f"Unknown tool: {name}"

    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        tools=[types.Tool(function_declarations=_TOOLS_DECL)],
    )
    contents: list = [
        types.Content(role="user", parts=[types.Part.from_text(task)])
    ]

    if on_step:
        on_step("Schedule Agent: checking inbox and calendar…")

    summary = ""
    for _guard in range(_MAX_ITER):
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        candidate = response.candidates[0]
        contents.append(candidate.content)

        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                summary = part.text

        fn_calls = [p.function_call for p in candidate.content.parts if p.function_call]
        if not fn_calls:
            break

        fn_response_parts: list[types.Part] = []
        for fc in fn_calls:
            args = dict(fc.args) if fc.args else {}
            if on_step:
                on_step(f"{fc.name}(…)")
            result = dispatch(fc.name, args)
            fn_response_parts.append(
                types.Part.from_function_response(name=fc.name, response={"result": result})
            )
        contents.append(types.Content(role="user", parts=fn_response_parts))

    return {"summary": summary, "proposed_actions": proposed_actions}
