"""Axolotl Orchestrator — decides which agents to invoke and synthesises results.

Gemini migration notes
──────────────────────
• Async Gemini client (client.aio.models.generate_content) so the event loop
  is never blocked by LLM calls.
• Sub-agents (web, email) remain synchronous and are called via run_in_executor
  so they also do not block the loop.
• Function calling replaces Anthropic tool_use:
    - Gemini returns function_call Parts in the candidate content.
    - Function responses go back as Part.from_function_response().
• System instruction moves from messages list into GenerateContentConfig.
• Adding a new agent: add one FunctionDeclaration to _TOOLS_DECL, handle the
  new name in _dispatch_tool, drop the agent module in /agents.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL
from agents import web_agent, email_agent

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
                "task": {
                    "type": "string",
                    "description": "Clear description of what to research",
                }
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
                }
            },
            "required": ["task"],
        },
    ),
]

_SYSTEM = (
    "You are Axolotl, a powerful AI orchestrator. You coordinate specialised agents "
    "to accomplish complex tasks.\n\n"
    "Your agents:\n"
    "  • Web Agent   — real-time web search and page reading\n"
    "  • Email Agent — professional email composition (requires user approval before sending)\n\n"
    "How to work:\n"
    "1. Analyse what the user needs.\n"
    "2. Delegate to the right agent(s) in the right order "
    "(e.g., research first, then email).\n"
    "3. Provide a brief status line before each delegation "
    "(\"Searching the web for…\").\n"
    "4. Synthesise a clear, friendly final answer once you have all results.\n\n"
    "Tone: confident, concise, like a capable personal assistant."
)

_GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM,
    tools=[types.Tool(function_declarations=_TOOLS_DECL)],
)

Emitter = Callable[[dict], Awaitable[None]]


# ── Main loop ──────────────────────────────────────────────────────────────────

async def run(user_message: str, emit: Emitter) -> None:
    """
    Drive the orchestration loop, streaming SSE events via emit().

    Event shapes
    ────────────
    {"type": "agent_start",  "agent": str, "message": str}
    {"type": "agent_step",   "agent": str, "message": str}
    {"type": "agent_result", "agent": str, "message": str}
    {"type": "email_draft",  "draft": {to, subject, body}, "draft_id": str}
    {"type": "token",        "agent": "orchestrator",      "text": str}
    {"type": "done",         "result": str}
    {"type": "error",        "message": str}
    """
    contents: list = [
        types.Content(role="user", parts=[types.Part.from_text(user_message)])
    ]
    loop = asyncio.get_running_loop()

    await emit({
        "type": "agent_start",
        "agent": "orchestrator",
        "message": "Axolotl is analysing your request…",
    })

    for _guard in range(20):  # hard cap on orchestration rounds
        response = await _get_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=_GEMINI_CONFIG,
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)

        # Emit any narrative text the orchestrator produced
        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                await emit({"type": "token", "agent": "orchestrator", "text": part.text})

        # Collect function calls
        fn_calls = [p.function_call for p in candidate.content.parts if p.function_call]

        if not fn_calls:
            # No more tool use — synthesise final answer
            final = " ".join(
                p.text for p in candidate.content.parts
                if hasattr(p, "text") and p.text
            ).strip()
            await emit({"type": "done", "result": final})
            return

        # Dispatch each function call and collect responses
        fn_response_parts: list[types.Part] = []
        for fc in fn_calls:
            task = dict(fc.args).get("task", "")
            result_str = await _dispatch_tool(fc.name, task, emit, loop)
            fn_response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result_str},
                )
            )

        contents.append(types.Content(role="user", parts=fn_response_parts))

    await emit({"type": "error", "message": "Orchestrator: maximum rounds reached."})


# ── Tool dispatcher ────────────────────────────────────────────────────────────

async def _dispatch_tool(
    tool_name: str,
    task: str,
    emit: Emitter,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """Run a sub-agent and return its string result for the function response."""

    if tool_name == "delegate_to_web_agent":
        await emit({
            "type": "agent_start",
            "agent": "web",
            "message": f"Web Agent: {task[:120]}",
        })

        def on_web_step(step: str) -> None:
            # Called from worker thread — safely schedule the coroutine
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "web", "message": step}),
                loop,
            )

        result: str = await loop.run_in_executor(
            None, lambda: web_agent.run(task, on_web_step)
        )

        await emit({
            "type": "agent_result",
            "agent": "web",
            "message": f"Web Agent finished. {result[:120]}…",
        })
        return result

    if tool_name == "delegate_to_email_agent":
        await emit({
            "type": "agent_start",
            "agent": "email",
            "message": "Email Agent: composing draft…",
        })

        def on_email_step(step: str) -> None:
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "email", "message": step}),
                loop,
            )

        draft: dict = await loop.run_in_executor(
            None, lambda: email_agent.run(task, on_email_step)
        )

        # The draft_id is stamped by main.py when it persists the draft
        await emit({"type": "email_draft", "draft": draft})

        summary = (
            f"Email draft ready — to: {draft.get('to', '?')}, "
            f"subject: '{draft.get('subject', '?')}'. Awaiting user approval."
        )
        await emit({"type": "agent_result", "agent": "email", "message": summary})
        return summary

    return f"Unknown tool: {tool_name}"
