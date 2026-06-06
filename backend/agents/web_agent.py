"""Web Agent — searches the web and fetches pages to answer research tasks.

Runs synchronously (called from orchestrator via run_in_executor so it doesn't
block the event loop). Uses the Gemini sync client directly.
"""
from __future__ import annotations

from typing import Callable

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL
from tools import web_tools

_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


_SYSTEM = (
    "You are the Web Agent, a focused web researcher. "
    "Find accurate, up-to-date information using your search and browsing tools.\n\n"
    "Process:\n"
    "1. Search for the topic with a precise query.\n"
    "2. If a result looks highly relevant, fetch the page for more detail.\n"
    "3. Synthesise a clear, concise answer with sources (URLs).\n\n"
    "Be factual. Always include the URLs you used so the reader can verify."
)

_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM,
    tools=[web_tools.GEMINI_TOOL],
)

_MAX_ITERATIONS = 10  # safety cap on the function-calling loop


def run(task: str, on_step: Callable[[str], None] | None = None) -> str:
    """Run the web agent synchronously.  on_step is called for live progress."""
    contents: list = [
        types.Content(role="user", parts=[types.Part.from_text(task)])
    ]

    for iteration in range(_MAX_ITERATIONS):
        if on_step:
            on_step(f"Researching: {task[:80]}")

        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=_CONFIG,
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)

        # Collect any function calls in this response
        fn_calls = [
            p.function_call
            for p in candidate.content.parts
            if p.function_call
        ]

        if not fn_calls:
            # No more tool calls → extract final text answer
            return (
                " ".join(
                    p.text for p in candidate.content.parts
                    if hasattr(p, "text") and p.text
                ).strip()
                or "Web Agent returned no text."
            )

        # Dispatch every function call and collect responses
        fn_response_parts: list[types.Part] = []
        for fc in fn_calls:
            args = dict(fc.args)
            if on_step:
                on_step(f"{fc.name}({str(args)[:60]}…)")
            result = web_tools.dispatch(fc.name, args)
            fn_response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
            )

        contents.append(types.Content(role="user", parts=fn_response_parts))

    return "Web Agent: maximum iterations reached without a final answer."
