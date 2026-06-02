"""Web-agent orchestration loop (ReAct-style, local + free).

The web agent (the scout that reports to Jarvis) can emit a control token when it
needs live information:

    [SEARCH: best open-source vector databases 2026]
    [VISIT: https://example.com/article]

This runner intercepts those tokens, executes them against the LOCAL headless
browser (services.local_browser — no paid API), appends the retrieved context as
an OBSERVATION into the running transcript, and triggers the next turn. When the
model replies with no token, that reply is the final answer.

`generate_fn` is injectable so the loop is unit-testable without a live model;
by default it routes through the web agent's voice (gemini.generate_for_agent),
so the synthesis sounds like the user.
"""
from __future__ import annotations

import re
from typing import Callable

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, User
from app.models.agent import AgentRole

logger = get_logger("axolot.web_research")

# Matches [SEARCH: ...] or [VISIT: ...] (first occurrence wins).
TOKEN_RE = re.compile(r"\[(SEARCH|VISIT):\s*(.+?)\]", re.IGNORECASE | re.DOTALL)

# Per-observation cap so a long page doesn't blow the prompt budget across steps.
_OBS_CAP = 3000

PROTOCOL = (
    "You are the user's web scout. You can use the live web with control tokens:\n"
    "  [SEARCH: <query>]  — search the web and read result titles/snippets.\n"
    "  [VISIT: <url>]     — open a page and read its cleaned text.\n"
    "Rules:\n"
    "- Emit EXACTLY ONE token on a line by itself when you need information, then stop.\n"
    "- After you receive OBSERVATION text, either search/visit again or, when you "
    "have enough, write your FINAL ANSWER with NO token — a tight synthesis in the "
    "user's voice, citing the URLs you used.\n"
    "- Never invent facts or URLs; ground every claim in an OBSERVATION."
)


def _web_agent(db: Session, user_id: str) -> Agent | None:
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == AgentRole.web.value)
        .first()
    )


def _default_generate(db: Session, agent: Agent | None) -> Callable[[str], str]:
    from app.services.gemini import generate, generate_for_agent

    def _fn(prompt: str) -> str:
        if agent is not None:
            return (generate_for_agent(db, agent, prompt, response_format="text") or "").strip()
        return (generate(prompt, response_format="text") or "").strip()

    return _fn


def _run_token(action: str, arg: str, max_results: int) -> tuple[str, list[str]]:
    """Execute one control token. Returns (observation_text, source_urls).

    SEARCH routes through agent_web.web_search so it honours the configured
    provider AND stub mode (hermetic dev/tests). VISIT scrapes via the local
    headless browser, with a stub observation under USE_STUBS."""
    from app.core.config import settings

    if action == "SEARCH":
        from app.services.agent_web import web_search

        results = web_search(arg, max_results=max_results)
        if not results:
            return (f"No results for '{arg}'.", [])
        lines = [f"{i+1}. {r['title']}\n   {r['url']}\n   {r.get('snippet', '')}" for i, r in enumerate(results)]
        return ("\n".join(lines)[:_OBS_CAP], [r["url"] for r in results])

    # VISIT
    if settings.USE_STUBS:
        return (f"[stub page] Representative cleaned text from {arg} for offline tests.", [arg])
    from app.services.local_browser import scrape_url

    page = scrape_url(arg)
    if not page.get("text"):
        return (f"Could not read {arg} ({page.get('error', 'unreachable')}).", [])
    body = page.get("markdown") or page.get("text")
    header = f"Title: {page.get('title', '')}\nURL: {arg}\n\n"
    return ((header + body)[:_OBS_CAP], [arg])


def run_agent_loop(
    db: Session,
    agent: Agent | None,
    task: str,
    *,
    max_steps: int = 4,
    max_results: int = 4,
    generate_fn: Callable[[str], str] | None = None,
) -> dict:
    """Drive the search→visit→synthesise loop. Returns
    {answer, steps:[{action,input,observation}], sources:[...], used_web:bool}.
    Never raises."""
    gen = generate_fn or _default_generate(db, agent)
    transcript: list[str] = []
    steps: list[dict] = []
    sources: list[str] = []

    def _prompt(closing: str) -> str:
        body = "\n\n".join(transcript)
        return f"{PROTOCOL}\n\nTask: {task}\n\n{body}\n\n{closing}"

    for step in range(max_steps):
        try:
            out = gen(_prompt("Your move:"))
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "web_loop_generate_failed", error=str(exc)[:160])
            break

        match = TOKEN_RE.search(out or "")
        if not match:
            log_event(logger, "web_loop_done", steps=len(steps), sources=len(sources))
            return {"answer": (out or "").strip(), "steps": steps, "sources": _dedupe(sources), "used_web": bool(steps)}

        action = match.group(1).upper()
        arg = match.group(2).strip()
        observation, srcs = _run_token(action, arg, max_results)
        sources.extend(srcs)
        steps.append({"action": action, "input": arg, "observation": observation[:500]})
        transcript.append(f"ASSISTANT: {out.strip()}")
        transcript.append(f"OBSERVATION:\n{observation}")
        log_event(logger, "web_loop_step", step=step, action=action, arg=arg[:120])

    # Out of steps (or generate failed mid-loop) — force a final synthesis.
    try:
        final = gen(_prompt("Write your FINAL ANSWER now in the user's voice, with NO token. Cite the URLs you used."))
    except Exception:  # noqa: BLE001
        final = ""
    if not final:
        final = "I gathered some sources but couldn't fully synthesise them — here are the links I pulled."
    return {"answer": final.strip(), "steps": steps, "sources": _dedupe(sources), "used_web": bool(steps)}


def _dedupe(urls: list[str]) -> list[str]:
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def deep_research(db: Session, user: User, query: str, *, max_steps: int = 4) -> dict:
    """Public entry: run the web agent's research loop for `user`. Jarvis routes
    here for 'find me X' requests. Returns the loop result dict."""
    agent = _web_agent(db, user.id)
    result = run_agent_loop(db, agent, query, max_steps=max_steps)
    log_event(logger, "deep_research", user_id=user.id, used_web=result["used_web"], sources=len(result["sources"]))
    return result
