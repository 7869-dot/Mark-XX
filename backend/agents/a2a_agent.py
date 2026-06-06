"""A2A Negotiation Agent — bounded inter-agent collaboration negotiation.

Follows the existing agent pattern (sync loop, module-level _client/MODEL).

Safety properties enforced here
────────────────────────────────
• Each agent's Claude call receives ONLY its own user's public AgentCard fields
  in its system prompt — the other party's data is never injected there.
• The shared transcript contains only what each agent chose to say publicly.
• turn cap (A2A_MAX_TURNS) is hard-coded in the loop condition.
• token ceiling (A2A_TURN_TOKENS) is set on every create() call.
• verdict is a structured tool call — no free-form output escapes.
"""
from __future__ import annotations

from typing import Callable

import anthropic

from config import ANTHROPIC_API_KEY, MODEL, A2A_MAX_TURNS, A2A_TURN_TOKENS

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Prompt builders ────────────────────────────────────────────────────────────

def _system_for(card: dict, my_role: str) -> str:
    other = "B" if my_role == "A" else "A"
    return (
        f"You are Agent {my_role}, the AI representative of a builder with this public profile:\n\n"
        f"  Name:        {card['display_name']}\n"
        f"  Building:    {card['building']}\n"
        f"  Looking for: {card['looking_for']}\n"
        f"  Can offer:   {card['can_offer']}\n"
        f"  Bio:         {card['public_bio']}\n\n"
        f"You are in a structured, time-boxed discussion with Agent {other}, who represents another builder.\n\n"
        "Rules:\n"
        "• Speak only from your own public profile — share nothing private.\n"
        "• Be specific: name real skills, timelines, complementary needs.\n"
        "• Each message ≤ 120 words.  Stay professional and direct.\n"
        f"• You do NOT know Agent {other}'s real name, email, or any private detail."
    )


_VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": (
        "Submit a structured verdict on whether the two agents' users should connect. "
        "Called exactly once after reviewing the full negotiation transcript."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "collaborate": {
                "type": "boolean",
                "description": "True if a genuine collaboration is plausible",
            },
            "idea": {
                "type": "string",
                "description": "One concrete collaboration idea (≤ 60 words)",
            },
            "what_each_brings": {
                "type": "string",
                "description": "What Builder A brings + what Builder B brings (≤ 60 words)",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score 0.0–1.0",
            },
        },
        "required": ["collaborate", "idea", "what_each_brings", "confidence"],
    },
}

_JUDGE_TOOL = {
    "name": "submit_score",
    "description": "Submit your collaboration-likelihood score and a one-line reason.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score":  {"type": "number",  "description": "0.0 (no fit) – 1.0 (strong fit)"},
            "reason": {"type": "string",  "description": "One-line explanation"},
        },
        "required": ["score", "reason"],
    },
}


# ── Public API ─────────────────────────────────────────────────────────────────

def judge_match(card_a: dict, card_b: dict) -> tuple[float, str]:
    """Quick LLM pre-filter: score 0–1 whether the pair is worth negotiating.

    Uses tool_choice='any' to guarantee a structured response.
    Follows the existing sync agent pattern.
    """
    prompt = (
        "Evaluate whether these two builders could plausibly collaborate.\n\n"
        f"Builder A — {card_a['display_name']}\n"
        f"  Building:    {card_a['building']}\n"
        f"  Looking for: {card_a['looking_for']}\n"
        f"  Can offer:   {card_a['can_offer']}\n\n"
        f"Builder B — {card_b['display_name']}\n"
        f"  Building:    {card_b['building']}\n"
        f"  Looking for: {card_b['looking_for']}\n"
        f"  Can offer:   {card_b['can_offer']}\n\n"
        "Call submit_score with your assessment."
    )

    response = _client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=(
            "You are a startup ecosystem analyst. Assess collaboration fit between two builders. "
            "High score = strong complementarity of what each builds and needs."
        ),
        tools=[_JUDGE_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_score":
            return float(block.input.get("score", 0.0)), block.input.get("reason", "")

    return 0.0, "Could not evaluate"


def run_negotiation(
    card_a: dict,
    card_b: dict,
    on_step: Callable[[str], None] | None = None,
) -> dict:
    """
    Run the full bounded A2A negotiation.

    Each agent only receives its own card in its system prompt.
    The transcript is the shared conversation they exchange.

    Returns a verdict dict:
      {
        collaborate: bool,
        idea: str,
        what_each_brings: str,
        confidence: float,
        transcript: list[{role, content, turn}],
      }
    """
    sys_a = _system_for(card_a, "A")
    sys_b = _system_for(card_b, "B")

    # Agent A message history: A=assistant, B=user
    msgs_a: list[dict] = [
        {
            "role": "user",
            "content": (
                "Open the collaboration discussion. Briefly introduce your project and "
                "explain what kind of partner you're looking for."
            ),
        }
    ]
    # Agent B message history: B=assistant, A=user — populated turn by turn
    msgs_b: list[dict] = []

    transcript: list[dict] = []
    half = A2A_MAX_TURNS // 2  # each agent speaks this many times

    for turn_idx in range(half):
        # ── Agent A speaks ─────────────────────────────────────────────────
        if on_step:
            on_step(f"Turn {turn_idx * 2 + 1}/{A2A_MAX_TURNS}: Agent A thinking…")

        resp_a = _client.messages.create(
            model=MODEL,
            max_tokens=A2A_TURN_TOKENS,
            system=sys_a,
            messages=msgs_a,
        )
        text_a = next(
            (b.text for b in resp_a.content if hasattr(b, "text")), ""
        ).strip()
        transcript.append({"role": "agent_a", "content": text_a, "turn": turn_idx * 2})

        # Update A's history with its own reply
        msgs_a.append({"role": "assistant", "content": text_a})

        # Give A's message to B as a "user" turn
        if msgs_b:
            msgs_b.append({"role": "user", "content": text_a})
        else:
            msgs_b = [{"role": "user", "content": text_a}]

        # ── Agent B responds ───────────────────────────────────────────────
        if on_step:
            on_step(f"Turn {turn_idx * 2 + 2}/{A2A_MAX_TURNS}: Agent B thinking…")

        resp_b = _client.messages.create(
            model=MODEL,
            max_tokens=A2A_TURN_TOKENS,
            system=sys_b,
            messages=msgs_b,
        )
        text_b = next(
            (b.text for b in resp_b.content if hasattr(b, "text")), ""
        ).strip()
        transcript.append({"role": "agent_b", "content": text_b, "turn": turn_idx * 2 + 1})

        # Update both histories
        msgs_b.append({"role": "assistant", "content": text_b})
        msgs_a.append({"role": "user", "content": text_b})

    # ── Produce structured verdict ─────────────────────────────────────────
    if on_step:
        on_step("Producing collaboration verdict…")

    verdict = _produce_verdict(card_a, card_b, transcript)
    verdict["transcript"] = transcript
    return verdict


# ── Internal helpers ───────────────────────────────────────────────────────────

def _produce_verdict(card_a: dict, card_b: dict, transcript: list[dict]) -> dict:
    """Ask Claude to evaluate the transcript and return a structured verdict."""
    convo_text = "\n\n".join(
        f"{m['role'].upper().replace('_', ' ')}: {m['content']}"
        for m in transcript
    )

    prompt = (
        f"BUILDER A: {card_a['display_name']} — building: {card_a['building']}\n"
        f"BUILDER B: {card_b['display_name']} — building: {card_b['building']}\n\n"
        f"NEGOTIATION TRANSCRIPT:\n{convo_text}\n\n"
        "Based solely on this transcript and the public profiles above, "
        "call submit_verdict with your structured assessment."
    )

    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=(
            "You are an independent analyst evaluating an AI-to-AI collaboration negotiation. "
            "Be honest and specific. A low confidence score is fine when warranted."
        ),
        tools=[_VERDICT_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_verdict":
            return {
                "collaborate":      bool(block.input.get("collaborate", False)),
                "idea":             block.input.get("idea", ""),
                "what_each_brings": block.input.get("what_each_brings", ""),
                "confidence":       float(block.input.get("confidence", 0.0)),
            }

    return {"collaborate": False, "idea": "", "what_each_brings": "", "confidence": 0.0}
