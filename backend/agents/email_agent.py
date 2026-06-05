"""Email Agent — composes professional emails for user approval before sending."""
from typing import Callable
import anthropic
from config import ANTHROPIC_API_KEY, MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# The draft_email tool is the agent's only output mechanism.
# It does NOT send — it submits a draft to the orchestrator for user approval.
_TOOLS = [
    {
        "name": "draft_email",
        "description": (
            "Submit a complete email draft for user review and approval. "
            "The email will NOT be sent until the user explicitly confirms it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Plain-text email body"},
            },
            "required": ["to", "subject", "body"],
        },
    }
]

_SYSTEM = """You are the Email Agent, an expert email composer. You write clear, \
professional emails based on the provided content.

Rules:
- Always call draft_email with the completed email — never claim to have sent it.
- Subject lines should be specific and informative.
- Body should be well-structured: greeting, content, sign-off.
- Keep it concise but complete."""


def run(task: str, on_step: Callable[[str], None] | None = None) -> dict:
    """Run the email agent. Returns a draft dict {to, subject, body}."""
    messages: list[dict] = [{"role": "user", "content": task}]

    while True:
        if on_step:
            on_step("Composing email draft…")

        response = _client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use" and block.name == "draft_email":
                    return block.input  # {to, subject, body}

        # Fallback: agent responded with text instead of using the tool
        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            return {"to": "", "subject": "Draft", "body": text, "_fallback": True}
