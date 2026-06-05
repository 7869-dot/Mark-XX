"""Web Agent — searches the web and fetches pages to answer research tasks."""
import json
from typing import Callable
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from tools import web_tools

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """You are the Web Agent, a focused web researcher. You find accurate, \
up-to-date information using your search and browsing tools.

Process:
1. Search for the topic with a precise query.
2. If a result looks highly relevant, fetch the page for more detail.
3. Synthesise a clear, concise answer with sources (URLs).

Be factual. Always include the URLs you used so the reader can verify."""


def run(task: str, on_step: Callable[[str], None] | None = None) -> str:
    """Run the web agent synchronously. on_step is called for live progress updates."""
    messages: list[dict] = [{"role": "user", "content": task}]

    while True:
        if on_step:
            on_step(f"Researching: {task[:80]}")

        response = _client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM,
            tools=web_tools.TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return next(
                (b.text for b in response.content if hasattr(b, "text")),
                "Web Agent returned no text.",
            )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                args_preview = json.dumps(block.input)[:60]
                if on_step:
                    on_step(f"{block.name}({args_preview}…)")
                result = web_tools.dispatch(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
