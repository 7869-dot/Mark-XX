"""A2A Negotiation Agent â€” bounded inter-agent collaboration negotiation.

Gemini migration notes
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â€¢ sync Anthropic client  â†’  async Gemini client (client.aio.models.generate_content)
â€¢ tool_choice "any"      â†’  response_schema (Pydantic) for judge + verdict
â€¢ multi-turn negotiation â†’  plain generate_content (no tools; text-only turns)
â€¢ Called from the async matchmaker so ALL public functions are async.

Safety properties (unchanged from previous implementation)
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â€¢ Each agent's call receives ONLY its own user's public AgentCard in system prompt.
â€¢ Transcript contains only what each agent chose to say publicly.
â€¢ Hard turn cap: A2A_MAX_TURNS from config.
â€¢ Token ceiling: A2A_TURN_TOKENS on every generate call.
â€¢ Structured output via response_schema â€” verdict cannot be free-form text.
"""
from __future__ import annotations

import json
from typing import Callable

from google import genai
from google.genai import types
from pydantic import BaseModel

from config import GOOGLE_API_KEY, GEMINI_MODEL, A2A_MAX_TURNS, A2A_TURN_TOKENS

_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


# â”€â”€ Structured output schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _JudgeResult(BaseModel):
    score:  float
    reason: str


class _VerdictResult(BaseModel):
    collaborate:       bool
    idea:              str
    what_each_brings:  str
    confidence:        float


# â”€â”€ Prompt builders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _system_for(card: dict, my_role: str) -> str:
    other = "B" if my_role == "A" else "A"
    return (
        f"You are Agent {my_role}, the AI representative of a builder with this public profile:\n\n"
        f"  Name:        {card['display_name']}\n"
        f"  Building:    {card['building']}\n"
        f"  Looking for: {card['looking_for']}\n"
        f"  Can offer:   {card['can_offer']}\n"
        f"  Bio:         {card['public_bio']}\n\n"
        f"You are in a structured, time-boxed discussion with Agent {other}.\n\n"
        "Rules:\n"
        "â€¢ Speak only from your own public profile â€” share nothing private.\n"
        "â€¢ Be specific: name real skills, timelines, complementary needs.\n"
        "â€¢ Each message â‰¤ 120 words. Stay professional and direct.\n"
        f"â€¢ You do NOT know Agent {other}'s real name, email, or any private detail."
    )


# â”€â”€ Public API (all async â€” called from async matchmaker) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def judge_match(card_a: dict, card_b: dict) -> tuple[float, str]:
    """LLM pre-filter: score 0â€“1 whether the pair is worth a full negotiation.

    Uses response_schema to guarantee a structured JSON response.
    """
    prompt = (
        "Evaluate whether these two builders could plausibly collaborate.\n\n"
        f"Builder A â€” {card_a['display_name']}\n"
        f"  Building:    {card_a['building']}\n"
        f"  Looking for: {card_a['looking_for']}\n"
        f"  Can offer:   {card_a['can_offer']}\n\n"
        f"Builder B â€” {card_b['display_name']}\n"
        f"  Building:    {card_b['building']}\n"
        f"  Looking for: {card_b['looking_for']}\n"
        f"  Can offer:   {card_b['can_offer']}\n\n"
        "Give a score (0.0 = no fit, 1.0 = strong fit) and a one-line reason."
    )

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a startup ecosystem analyst. Score collaboration fit between two builders. "
            "High score = strong complementarity of what each builds and needs."
        ),
        response_mime_type="application/json",
        response_schema=_JudgeResult,
    )

    response = await _get_client().aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )

    try:
        data = json.loads(response.text)
        return float(data.get("score", 0.0)), data.get("reason", "")
    except Exception:
        return 0.0, "Could not evaluate"


async def run_negotiation(
    card_a: dict,
    card_b: dict,
    on_step: Callable[[str], None] | None = None,
) -> dict:
    """Run the full bounded A2A negotiation (async).

    Each agent only receives its own card in its system prompt.
    The shared transcript is built turn by turn.

    Returns:
      {
        collaborate: bool,  idea: str,
        what_each_brings: str,  confidence: float,
        transcript: list[{role, content, turn}],
      }
    """
    config_a = types.GenerateContentConfig(
        system_instruction=_system_for(card_a, "A"),
        max_output_tokens=A2A_TURN_TOKENS,
    )
    config_b = types.GenerateContentConfig(
        system_instruction=_system_for(card_b, "B"),
        max_output_tokens=A2A_TURN_TOKENS,
    )

    # Agent A starts; B's history grows as A speaks
    msgs_a: list = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(
                "Open the collaboration discussion. Briefly introduce your project "
                "and explain what kind of partner you are looking for."
            )],
        )
    ]
    msgs_b: list = []
    transcript: list[dict] = []
    half = A2A_MAX_TURNS // 2

    for turn_idx in range(half):
        # â”€â”€ Agent A speaks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if on_step:
            on_step(f"Turn {turn_idx * 2 + 1}/{A2A_MAX_TURNS}: Agent A thinkingâ€¦")

        resp_a = await _get_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=msgs_a,
            config=config_a,
        )
        text_a = _extract_text(resp_a)
        transcript.append({"role": "agent_a", "content": text_a, "turn": turn_idx * 2})

        # Update A's history
        msgs_a.append(resp_a.candidates[0].content)

        # Give A's message to B as a user turn
        a_part = types.Content(
            role="user",
            parts=[types.Part.from_text(text_a)],
        )
        if msgs_b:
            msgs_b.append(a_part)
        else:
            msgs_b = [a_part]

        # â”€â”€ Agent B responds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if on_step:
            on_step(f"Turn {turn_idx * 2 + 2}/{A2A_MAX_TURNS}: Agent B thinkingâ€¦")

        resp_b = await _get_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=msgs_b,
            config=config_b,
        )
        text_b = _extract_text(resp_b)
        transcript.append({"role": "agent_b", "content": text_b, "turn": turn_idx * 2 + 1})

        # Update both histories
        msgs_b.append(resp_b.candidates[0].content)
        msgs_a.append(
            types.Content(role="user", parts=[types.Part.from_text(text_b)])
        )

    # â”€â”€ Structured verdict â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if on_step:
        on_step("Producing collaboration verdictâ€¦")

    verdict = await _produce_verdict(card_a, card_b, transcript)
    verdict["transcript"] = transcript
    return verdict


# â”€â”€ Internal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _extract_text(response) -> str:
    """Pull all text parts from a GenerateContentResponse."""
    parts = response.candidates[0].content.parts
    return " ".join(
        p.text for p in parts if hasattr(p, "text") and p.text
    ).strip()


async def _produce_verdict(
    card_a: dict,
    card_b: dict,
    transcript: list[dict],
) -> dict:
    """Ask Gemini to evaluate the transcript and return a structured verdict."""
    convo_text = "\n\n".join(
        f"{m['role'].upper().replace('_', ' ')}: {m['content']}"
        for m in transcript
    )

    prompt = (
        f"BUILDER A: {card_a['display_name']} â€” building: {card_a['building']}\n"
        f"BUILDER B: {card_b['display_name']} â€” building: {card_b['building']}\n\n"
        f"NEGOTIATION TRANSCRIPT:\n{convo_text}\n\n"
        "Based solely on this transcript and the public profiles above, "
        "evaluate whether these builders should connect."
    )

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are an independent analyst evaluating an AI-to-AI collaboration negotiation. "
            "Be honest and specific. A low confidence score is fine when warranted."
        ),
        response_mime_type="application/json",
        response_schema=_VerdictResult,
    )

    response = await _get_client().aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )

    try:
        data = json.loads(response.text)
        return {
            "collaborate":      bool(data.get("collaborate", False)),
            "idea":             data.get("idea", ""),
            "what_each_brings": data.get("what_each_brings", ""),
            "confidence":       float(data.get("confidence", 0.0)),
        }
    except Exception:
        return {"collaborate": False, "idea": "", "what_each_brings": "", "confidence": 0.0}
