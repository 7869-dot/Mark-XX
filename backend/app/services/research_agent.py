"""Research agent — Jarvis as a research partner, not a search engine (Sprint 3A).

Web search (reuses agent_web.web_search — Tavily/SerpAPI with stub fallback) is
synthesized through Jarvis in the user's voice: a verbal briefing, not a report.
Results are ephemeral — displayed inline in chat, never stored, no approval.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent
from app.models.agent import AgentRole

logger = get_logger("axolot.research_agent")


def _jarvis(db: Session, user_id: str) -> Agent | None:
    for role in (AgentRole.jarvis, AgentRole.feed):
        a = db.query(Agent).filter(
            Agent.user_id == user_id, Agent.role == role.value
        ).first()
        if a:
            return a
    return None


def research(db: Session, query: str, user_id: str) -> dict:
    """Return {query, synthesis, key_points, sources, follow_up_questions}.
    Never raises — degrades to a plain synthesis with no sources on failure."""
    from app.services.agent_web import web_search

    results = web_search(query, max_results=5)
    sources = [r.get("url", "") for r in results if r.get("url")]
    source_block = "\n".join(f"- {r['title']}: {r['snippet']}" for r in results) or "(no live results)"

    agent = _jarvis(db, user_id)
    synthesis, key_points, follow_ups = "", [], []
    if agent:
        instruction = (
            f"You're researching this for your user: \"{query}\".\n"
            "Synthesize the results below for them specifically — lead with what's "
            "most relevant, skip the obvious, write like you're briefing them out "
            "loud (not a report). Return ONLY valid JSON with keys: synthesis "
            "(2-4 sentences), key_points (3-5 bullets), follow_up_questions (2-3 "
            "questions they should ask next). No preamble.\n\n"
            f"Raw results:\n{source_block}"
        )
        try:
            from app.services.gemini import generate_for_agent, extract_json

            data = extract_json(generate_for_agent(db, agent, instruction, response_format="research"))
            synthesis = str(data.get("synthesis", "")).strip()
            key_points = [str(k).strip() for k in (data.get("key_points") or []) if str(k).strip()][:5]
            follow_ups = [str(q).strip() for q in (data.get("follow_up_questions") or []) if str(q).strip()][:3]
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "research_synthesis_failed", user_id=user_id, error=str(exc))

    if not synthesis:
        # Honest, not fabricated: we have the sources but no model synthesis.
        synthesis = (
            f"I pulled these sources on {query} but couldn't synthesise them just "
            "now — the model didn't return a usable response. The links are below."
        )
    log_event(logger, "research_done", user_id=user_id, sources=len(sources))
    return {
        "query": query,
        "synthesis": synthesis,
        "key_points": key_points,
        "sources": sources,
        "follow_up_questions": follow_ups,
    }
