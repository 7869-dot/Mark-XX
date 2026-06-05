"""Axolotl Orchestrator — decides which agents to invoke and synthesises results."""
import asyncio
from typing import Callable, Awaitable
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from agents import web_agent, email_agent

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# To add a new agent: add its tool here, handle it in _dispatch_tool, and drop its
# module in /agents. Nothing else needs changing.
_TOOLS = [
    {
        "name": "delegate_to_web_agent",
        "description": (
            "Delegate a research or information-retrieval task to the Web Agent. "
            "Use when the user needs current information, news, facts, or any web content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of what to research",
                }
            },
            "required": ["task"],
        },
    },
    {
        "name": "delegate_to_email_agent",
        "description": (
            "Delegate email drafting to the Email Agent. The agent will compose a draft "
            "and return it for user approval — the email is NOT sent automatically."
        ),
        "input_schema": {
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
    },
]

_SYSTEM = """You are Axolotl, a powerful AI orchestrator. You coordinate specialised agents \
to accomplish complex tasks.

Your agents:
  • Web Agent  — real-time web search and page reading
  • Email Agent — professional email composition (requires user approval before sending)

How to work:
1. Analyse what the user needs.
2. Delegate to the right agent(s) in the right order (e.g., research first, then email).
3. Provide a brief status line before each delegation ("Searching the web for…").
4. Synthesise a clear, friendly final answer once you have all results.

Tone: confident, concise, like a capable personal assistant."""

Emitter = Callable[[dict], Awaitable[None]]


async def run(user_message: str, emit: Emitter) -> None:
    """
    Drive the full orchestration loop, streaming SSE events via emit().

    Event shapes
    ────────────
    {"type": "agent_start",  "agent": str, "message": str}
    {"type": "agent_step",   "agent": str, "message": str}
    {"type": "agent_result", "agent": str, "message": str}
    {"type": "email_draft",  "draft": {to,subject,body}, "draft_id": str}
    {"type": "token",        "agent": "orchestrator",    "text": str}
    {"type": "done",         "result": str}
    {"type": "error",        "message": str}
    """
    messages: list[dict] = [{"role": "user", "content": user_message}]
    loop = asyncio.get_running_loop()

    await emit(
        {
            "type": "agent_start",
            "agent": "orchestrator",
            "message": "Axolotl is analysing your request…",
        }
    )

    while True:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        # Stream any narrative text the orchestrator produced
        for block in response.content:
            if hasattr(block, "text") and block.text:
                await emit({"type": "token", "agent": "orchestrator", "text": block.text})

        if response.stop_reason == "end_turn":
            final = " ".join(
                b.text for b in response.content if hasattr(b, "text")
            ).strip()
            await emit({"type": "done", "result": final})
            return

        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                task = block.input.get("task", "")
                result_content = await _dispatch_tool(
                    block.name, task, block.id, emit, loop
                )
                tool_results.append(result_content)

            messages.append({"role": "user", "content": tool_results})


async def _dispatch_tool(
    tool_name: str,
    task: str,
    tool_use_id: str,
    emit: Emitter,
    loop: asyncio.AbstractEventLoop,
) -> dict:
    """Run a sub-agent and return the tool_result block for the orchestrator."""

    if tool_name == "delegate_to_web_agent":
        await emit(
            {"type": "agent_start", "agent": "web", "message": f"Web Agent: {task[:120]}"}
        )

        steps: list[str] = []

        def on_web_step(step: str) -> None:
            # Called from worker thread — schedule the emit coroutine on the event loop
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "web", "message": step}),
                loop,
            )

        result: str = await loop.run_in_executor(
            None, lambda: web_agent.run(task, on_web_step)
        )

        await emit(
            {
                "type": "agent_result",
                "agent": "web",
                "message": f"Web Agent finished. {result[:120]}…",
            }
        )
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": result}

    if tool_name == "delegate_to_email_agent":
        await emit(
            {"type": "agent_start", "agent": "email", "message": "Email Agent: composing draft…"}
        )

        def on_email_step(step: str) -> None:
            asyncio.run_coroutine_threadsafe(
                emit({"type": "agent_step", "agent": "email", "message": step}),
                loop,
            )

        draft: dict = await loop.run_in_executor(
            None, lambda: email_agent.run(task, on_email_step)
        )

        # Emit the draft for the frontend to render a confirmation UI.
        # The draft_id is assigned by main.py when it persists the draft.
        await emit({"type": "email_draft", "draft": draft})

        summary = (
            f"Email draft ready — to: {draft.get('to', '?')}, "
            f"subject: '{draft.get('subject', '?')}'. Awaiting user approval."
        )
        await emit({"type": "agent_result", "agent": "email", "message": summary})

        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": summary,
        }

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": f"Unknown tool: {tool_name}",
    }
