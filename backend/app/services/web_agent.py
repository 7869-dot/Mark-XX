"""Web Scout sub-agent (Section 3, sub-agent 3) — the strongest sub-agent.

Continuously scans the web for opportunities tailored to the user's memory
profile (interests, goals, opportunity_preferences), across six categories:
freelance, learning, certification, news, investment, event. Results are stored
in web_scout_results with a relevance_score; the agent reports the top 5 to
Jarvis as structured JSON.

Adaptive learning: it reads the rolling feedback_log (via user_profile
.category_weights) and re-weights categories — surfacing more of what the user
upvotes and suppressing what they dismiss.

Search uses agent_web.web_search (Tavily/SerpAPI with httpx + deterministic stub
fallback), so it works end-to-end with no external key. Relevance ranking uses
the heavy Gemini tier, with a deterministic heuristic fallback so it never hangs.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, User, UserProfile, WebScoutResult, WEB_CATEGORIES
from app.models.agent import AgentRole
from app.services import user_profile as profiles
from app.services.agent_runs import WEB_AGENT, log_run

logger = get_logger("axolot.web_agent")

# Query template per category. {interest} is filled from the user's top interest.
_QUERY_TEMPLATES = {
    "freelance": "{interest} freelance gigs or remote contract jobs hiring",
    "learning": "best {interest} courses tutorials and papers to learn 2026",
    "certification": "{interest} professional certification or certificate program",
    "news": "{interest} latest news and trends 2026",
    "investment": "{interest} income or investment opportunities",
    "event": "{interest} hackathon competition or conference 2026",
}

# How far back to dedupe by URL so a scan doesn't re-store the same find.
_DEDUPE_WINDOW = timedelta(hours=36)


def _web_agent(db: Session, user_id: str) -> Agent | None:
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == AgentRole.web.value)
        .first()
    )


def _interests_for(profile: UserProfile | None) -> list[str]:
    interests = [str(i).strip() for i in ((profile.interests if profile else []) or []) if str(i).strip()]
    goals = (profile.goals if profile else {}) or {}
    for k in ("current_focus", "improve", "this_month"):
        v = str(goals.get(k, "") or "").strip()
        if v:
            interests.append(v)
    return interests or ["technology"]


def _recent_urls(db: Session, user_id: str) -> set[str]:
    cutoff = datetime.utcnow() - _DEDUPE_WINDOW
    rows = (
        db.query(WebScoutResult.url)
        .filter(WebScoutResult.user_id == user_id, WebScoutResult.created_at >= cutoff)
        .all()
    )
    return {r[0] for r in rows if r[0]}


def _heuristic_score(category: str, weight: float, rank: int) -> float:
    """Deterministic relevance when the LLM ranker is unavailable: category
    feedback-weight dominates, position is a small tiebreak."""
    return round(max(0.05, min(0.95, 0.45 * weight + max(0.0, 0.4 - 0.05 * rank))), 2)


def _rank_with_llm(db: Session, agent: Agent | None, profile: UserProfile | None,
                   candidates: list[dict]) -> dict[int, dict]:
    """Ask the heavy tier to score each candidate 0-1 for THIS user and write a
    one-sentence summary. Returns {index: {relevance, summary}}. Empty on any
    failure (caller falls back to the heuristic)."""
    if not agent or not candidates:
        return {}
    p = profiles.profile_dict(profile)
    listing = "\n".join(
        f"{i}. [{c['category']}] {c['title']} — {c['snippet']}" for i, c in enumerate(candidates)
    )
    instruction = (
        "You are the user's web scout. Score how relevant each item below is to "
        "THIS user, and write a one-sentence summary of why it matters to them.\n\n"
        f"User interests: {p['interests']}\nGoals: {p['goals']}\n"
        f"They dislike / want to avoid: {p['hates']}\n\n"
        "Return ONLY valid JSON: a list of objects "
        "{\"index\": <int>, \"relevance\": <0..1 float>, \"summary\": \"<one sentence>\"}. "
        "Be ruthless — low scores for anything off-target.\n\n"
        f"Items:\n{listing}"
    )
    try:
        from app.services.gemini import generate_for_agent, extract_json

        raw = generate_for_agent(db, agent, instruction, response_format="web_relevance")
        data = extract_json(raw)
        out: dict[int, dict] = {}
        for entry in data if isinstance(data, list) else []:
            idx = int(entry.get("index"))
            out[idx] = {
                "relevance": max(0.0, min(1.0, float(entry.get("relevance", 0.5)))),
                "summary": str(entry.get("summary", "")).strip(),
            }
        return out
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "web_rank_fallback", error=str(exc))
        return {}


def run_report(db: Session, user: User, *, per_category: int = 3, top_n: int = 5) -> dict:
    """Scan the user's active categories, store finds, and report the top finds.

    Returns {"top_finds": [{id, title, url, summary, category, relevance_score}],
             "scanned_categories": [...], "stored": <int>}. Never raises —
    logs an AgentRunLog row (status 'ok'/'error') as a side effect.
    """
    from app.services.agent_web import web_search

    profile = profiles.get_or_create_profile(db, user)
    agent = _web_agent(db, user.id)
    weights = profiles.category_weights(profile)
    categories = profiles.active_categories(profile)
    # Adaptive: drop categories the user has dismissed hard, unless that would
    # leave nothing to scan.
    kept = [c for c in categories if weights.get(c, 1.0) >= 0.4] or categories

    interests = _interests_for(profile)
    primary = interests[0]
    seen_urls = _recent_urls(db, user.id)

    candidates: list[dict] = []
    for cat in kept:
        template = _QUERY_TEMPLATES.get(cat, "{interest} " + cat)
        query = template.format(interest=primary)
        try:
            results = web_search(query, max_results=per_category)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "web_scan_failed", category=cat, error=str(exc))
            results = []
        for r in results:
            url = (r.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append({
                "title": (r.get("title") or "").strip()[:300],
                "url": url,
                "snippet": (r.get("snippet") or "").strip(),
                "category": cat,
            })

    ranked = _rank_with_llm(db, agent, profile, candidates) if candidates else {}

    stored_rows: list[WebScoutResult] = []
    for i, c in enumerate(candidates):
        info = ranked.get(i, {})
        relevance = info.get("relevance")
        if relevance is None:
            relevance = _heuristic_score(c["category"], weights.get(c["category"], 1.0), i)
        else:
            # Blend the model score with the feedback weight so learning sticks.
            relevance = round(max(0.05, min(0.99, relevance * weights.get(c["category"], 1.0))), 2)
        summary = info.get("summary") or (c["snippet"][:160] or c["title"])
        row = WebScoutResult(
            user_id=user.id,
            title=c["title"],
            url=c["url"],
            summary=summary,
            category=c["category"],
            relevance_score=relevance,
        )
        db.add(row)
        stored_rows.append(row)
    if stored_rows:
        db.commit()
        for row in stored_rows:
            db.refresh(row)

    # Report the standing top finds "since last session" — the most relevant
    # results from the recent window, not only what this scan freshly stored
    # (so a dedup'd re-run still surfaces the user's best opportunities).
    window_start = datetime.utcnow() - timedelta(days=7)
    top = (
        db.query(WebScoutResult)
        .filter(WebScoutResult.user_id == user.id, WebScoutResult.created_at >= window_start)
        .order_by(WebScoutResult.relevance_score.desc(), WebScoutResult.created_at.desc())
        .limit(top_n)
        .all()
    )
    top_finds = [
        {
            "id": r.id,
            "title": r.title,
            "url": r.url,
            "summary": r.summary,
            "category": r.category,
            "relevance_score": r.relevance_score,
        }
        for r in top
    ]

    summary_line = (
        f"Scanned {len(kept)} categories, surfaced {len(top_finds)} high-signal finds "
        f"(top: {top_finds[0]['title']})." if top_finds else "Scan complete; nothing high-signal."
    )
    log_run(db, user.id, WEB_AGENT, summary_line, status="ok")
    log_event(logger, "web_report", user_id=user.id, stored=len(stored_rows), top=len(top_finds))
    return {"top_finds": top_finds, "scanned_categories": kept, "stored": len(stored_rows)}
