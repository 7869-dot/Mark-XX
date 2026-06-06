"""Jarvis — Chief of Staff orchestrator.

Coordinates all sub-agents and surfaces proposed actions for user approval.

Agents
──────
• Web Agent          — real-time search + page reading
• Schedule Agent     — inbox + calendar; drafts replies and proposes events
• Connection Agent   — surfaces and triggers new founder matches

Tools
─────
• delegate_to_web_agent        — search and fetch web content
• delegate_to_schedule_agent   — check emails/calendar, draft actions
• delegate_to_connection_agent — run matchmaker on demand, surface unseen matches
• propose_action               — queue an approval card for the user

Persona: anticipatory, concise, proposes before being asked.

Adding a new agent: add one FunctionDeclaration to _TOOLS_DECL, handle the
new name in _dispatch_tool, drop the agent module in /agents.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Awaitable

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL
from agents import web_agent, email_agent

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
        name="delegate_to_web_agent",
        description=(
            "Delegate a research or information-retrieval task to the Web Agent. "
            "Use when the user needs current information, news, facts, or any web content."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Clear description of what to research"},
            },
            "required": ["task"],
        },
    ),
    types.FunctionDeclaration(
        name="delegate_to_email_agent",
        description=(
            "Delegate email drafting to the Email Agent. The agent will compose a draft "
            "and return it for user approval — the email is NOT sent automatically."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "Full description of the email to draft: recipient, subject, "
                        "content to include, and any relevant context or research results"
                    ),
                },
            },
            "required": ["task"],
        },
    ),
    types.FunctionDeclaration(
        name="delegate_to_schedule_agent",
        description=(
            "Delegate to the Schedule & Email Agent to check inbox and/or calendar. "
            "It can summarise unread emails, show today's schedule, draft email replies, "
            "and propose calendar events — all for user approval before anything is sent."
            " Requires the user to have connected their Google account."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "What to check or do: e.g. 'summarise my unread emails', "
                        "'show today's schedule', 'draft a reply to the email from Alex about the demo'"
                    ),
                },
            },
            "required": ["task"],
        },
    ),
    types.FunctionDeclaration(
        name="delegate_to_connection_agent",
        description=(
            "Delegate to the Connection Agent to surface founder matches. "
            "Triggers the matchmaker pipeline for the user and returns any new or unseen matches. "
            "Use when the user asks about connections, co-founders, or collaboration opportunities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Description of the connection request or match query",
                },
            },
            "required": ["task"],
        },
    ),
    types.FunctionDeclaration(
        name="propose_action",
        description=(
            "Queue a proposed action for the user's approval. Use this when Jarvis wants to "
            "proactively suggest something without being asked — an email reply, a calendar event, "
            "or a connection approval. The action is NOT executed until the user approves it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action_type": {
                    "type":        "string",
                    "enum":        ["email_reply", "calendar_event", "connection_approval"],
                    "description": "Type of action to propose",
                },
                "payload": {
                    "type":        "object",
                    "description": (
                        "Action details. "
                        "email_reply: {to, subject, body, in_reply_to_id?}. "
                        "calendar_event: {title, start, end, description?, attendees?}. "
                        "connection_approval: {briefing_id, proposal_id, partner_name, summary}."
                    ),
                },
                "rationale": {
                    "type":        "string",
                    "description": "Brief reason why Jarvis is proposing this action",
                },
            },
            "required": ["action_type", "payload"],
        },
    ),
]

_SYSTEM = (
    "You are Jarvis, an anticipatory chief-of-staff AI.\n\n"
    "Your agents:\n"
    "  • Web Agent          — real-time web search and page reading\n"
    "  • Schedule Agent     — inbox + calendar; drafts email replies, proposes events\n"
    "  • Connection Agent   — surfaces founder matches and collaboration opportunities\n\n"
    "Your tools:\n"
    "  • delegate_to_* tools — send tasks to sub-agents\n"
    "  • propose_action      — queue an approval card without executing it\n\n"
    "How to work:\n"
    "1. Anticipate what the user needs — offer insights before being asked.\n"
    "2. Delegate to the right agent(s) in the right order.\n"
    "3. Use propose_action when you spot something that needs attention "
    "   (a reply to send, a meeting to schedule) so the user can approve with one click.\n"
    "4. Synthesise a clear, concise answer once all agents respond.\n\n"
    "Tone: confident, direct, warm. Lead with what matters most. "
    "Propose things — don't just report. If you see an email needing a reply, "
    "draft it. If you see a scheduling conflict, flag it."
)

_GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM,
    tools=[types.Tool(function_declarations=_TOOLS_DECL)],
)

Emitter = Callable[[dict], Awaitable[None]]


# ── Main loop ──────────────────────────────────────────────────────────────────

async def run(
    user_message: str,
    emit: Emitter,
    user_id: str | None = None,
    access_token: str | None = None,
) -> None:
    """
    Drive the Jarvis orchestration loop, streaming SSE events via emit().

    user_id / access_token are optional; when present they unlock the schedule
    agent (Gmail/Calendar) and proposed_action persistence.

    Event shapes
    ────────────
    {"type": "agent_start",          "agent": str, "message": str}
    {"type": "agent_step",           "agent": str, "message": str}
    {"type": "agent_result",         "agent": str, "message": str}
    {"type": "email_draft",          "draft": {to, subject, body}, "draft_id": str}
    {"type": "proposed_action_created", "action": {id, type, payload, rationale}}
    {"type": "token",                "agent": "orchestrator", "text": str}
    {"type": "done",                 "result": str}
    {"type": "error",                "message": str}
    """
    contents: list = [
        types.Content(role="user", parts=[types.Part.from_text(user_message)])
    ]
    loop = asyncio.get_running_loop()

    await emit({
        "type":    "agent_start",
        "agent":   "orchestrator",
        "message": "Jarvis is thinking…",
    })

    for _guard in range(20):
        response = await _get_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=_GEMINI_CONFIG,
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)

        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                await emit({"type": "token", "agent": "orchestrator", "text": part.text})

        fn_calls = [p.function_call for p in candidate.content.parts if p.function_call]

        if not fn_calls:
            final = " ".join(
                p.text for p in candidate.content.parts
                if hasattr(p, "text") and p.text
            ).strip()
            await emit({"type": "done", "result": final})
            return

        fn_response_parts: list[types.Part] = []
        for fc in fn_calls:
            args = dict(fc.args) if fc.args else {}
            task = args.get("task", "")
            result_str = await _dispatch_tool(
                fc.name, task, args, emit, loop, user_id, access_token
            )
            fn_response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result_str},
                )
            )

        contents.append(types.Content(role="user", parts=fn_response_parts))

    await emit({"type": "error", "message": "Jarvis: maximum orchestration rounds reached."})


# ── Tool dispatcher ────────────────────────────────────────────────────────────

async def _dispatch_tool(
    tool_name:    str,
    task:         str,
    args:         dict,
    emit:         Emitter,
    loop:         asyncio.AbstractEventLoop,
    user_id:      str | None,
    access_token: str | None,
) -> str:

    # ── Web Agent ──────────────────────────────────────────────────────────────
    if tool_name == "delegate_to_web_agent":
        await emit({"type": "agent_start", "agent": "web", "message": f"Web Agent: {task[:120]}"})

        def on_web_step(step: str) -> None:
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "web", "message": step}), loop
            )

        result: str = await loop.run_in_executor(None, lambda: web_agent.run(task, on_web_step))
        await emit({"type": "agent_result", "agent": "web", "message": f"Web Agent finished. {result[:120]}…"})
        return result

    # ── Email Agent (legacy draft composer) ───────────────────────────────────
    if tool_name == "delegate_to_email_agent":
        await emit({"type": "agent_start", "agent": "email", "message": "Email Agent: composing draft…"})

        def on_email_step(step: str) -> None:
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "email", "message": step}), loop
            )

        draft: dict = await loop.run_in_executor(None, lambda: email_agent.run(task, on_email_step))
        await emit({"type": "email_draft", "draft": draft})
        summary = (
            f"Email draft ready — to: {draft.get('to', '?')}, "
            f"subject: '{draft.get('subject', '?')}'. Awaiting user approval."
        )
        await emit({"type": "agent_result", "agent": "email", "message": summary})
        return summary

    # ── Schedule Agent (Gmail + Calendar) ─────────────────────────────────────
    if tool_name == "delegate_to_schedule_agent":
        if not access_token:
            return "Schedule Agent unavailable: user has not connected their Google account."

        await emit({"type": "agent_start", "agent": "schedule", "message": f"Schedule Agent: {task[:120]}"})

        def on_schedule_step(step: str) -> None:
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "schedule", "message": step}), loop
            )

        from agents import schedule_agent
        result_dict: dict = await loop.run_in_executor(
            None, lambda: schedule_agent.run(task, access_token, on_schedule_step)
        )

        # Persist any proposed_actions the agent produced
        proposed = result_dict.get("proposed_actions", [])
        if proposed and user_id:
            await _persist_proposed_actions(proposed, user_id, emit)

        summary = result_dict.get("summary", "Schedule Agent completed.")
        await emit({"type": "agent_result", "agent": "schedule", "message": summary[:200]})
        return summary

    # ── Connection Agent (matchmaker) ─────────────────────────────────────────
    if tool_name == "delegate_to_connection_agent":
        if not user_id:
            return "Connection Agent unavailable: authentication required."

        await emit({"type": "agent_start", "agent": "connection", "message": "Connection Agent: scanning matches…"})

        def on_conn_step(step: str) -> None:
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "connection", "message": step}), loop
            )

        from agents import connection_agent
        result: str = await connection_agent.run(user_id, on_conn_step)
        await emit({"type": "agent_result", "agent": "connection", "message": result[:200]})
        return result

    # ── propose_action ─────────────────────────────────────────────────────────
    if tool_name == "propose_action":
        if not user_id:
            return "Cannot propose action: authentication required."

        action_type = args.get("action_type", "")
        payload     = args.get("payload", {})
        rationale   = args.get("rationale", "")

        action_id = await _save_and_emit_proposed_action(
            user_id, action_type, payload, rationale, emit
        )
        return f"Proposed action queued (id: {action_id}). Awaiting user approval."

    return f"Unknown tool: {tool_name}"


# ── Persistence helpers ────────────────────────────────────────────────────────

async def _persist_proposed_actions(
    actions: list[dict],
    user_id: str,
    emit:    Emitter,
) -> None:
    from db import SessionLocal
    from models import ProposedAction

    db = SessionLocal()
    try:
        for a in actions:
            action = ProposedAction(
                user_id=user_id,
                type=a.get("type", ""),
                payload=a.get("payload", {}),
                rationale=a.get("rationale", ""),
                status="pending",
            )
            db.add(action)
            db.flush()
            await emit({
                "type":   "proposed_action_created",
                "action": {
                    "id":        action.id,
                    "type":      action.type,
                    "payload":   action.payload,
                    "rationale": action.rationale,
                },
            })
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist proposed actions: %s", exc)
        db.rollback()
    finally:
        db.close()


async def _save_and_emit_proposed_action(
    user_id:     str,
    action_type: str,
    payload:     dict,
    rationale:   str,
    emit:        Emitter,
) -> str:
    from db import SessionLocal
    from models import ProposedAction

    db = SessionLocal()
    try:
        action = ProposedAction(
            user_id=user_id,
            type=action_type,
            payload=payload,
            rationale=rationale,
            status="pending",
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        await emit({
            "type":   "proposed_action_created",
            "action": {
                "id":        action.id,
                "type":      action.type,
                "payload":   action.payload,
                "rationale": action.rationale,
            },
        })
        return action.id
    except Exception as exc:
        logger.warning("Failed to save proposed action: %s", exc)
        db.rollback()
        return "unknown"
    finally:
        db.close()
