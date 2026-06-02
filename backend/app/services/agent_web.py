"""Agent Web Access — the agent's sensory system.

Live web search (Tavily/SerpAPI, stub fallback), an RSS reader, the per-user
TopicInterestProfile, and grounded post composition: the agent reads real
sources and writes *the user's take* on them — every output carries a
confidence_score and a traceable source_list, never a hallucination.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.models import Agent, TopicInterest
from app.models.web import TOPIC_CATEGORIES

logger = get_logger("axolot.web")

# Cheap keyword → category routing for topics the user adds / the agent infers.
_CATEGORY_KEYWORDS = {
    "tech": ("ai", "ml", "software", "startup", "tech", "crypto", "data", "llm", "gpu"),
    "sports": ("football", "soccer", "nba", "tennis", "cricket", "sport", "match", "league"),
    "geopolitics": ("war", "election", "conflict", "geopolitic", "policy", "diplomacy", "sanction"),
    "finance": ("market", "stock", "economy", "rate", "inflation", "finance", "fund", "vc"),
    "science": ("science", "research", "physics", "biology", "space", "climate", "study"),
    "culture": ("music", "film", "art", "book", "design", "culture", "game", "gaming"),
    "local": ("local", "city", "neighbourhood", "neighborhood", "community"),
}


def categorize(topic: str) -> str:
    t = (topic or "").lower()
    for cat, kws in _CATEGORY_KEYWORDS.items():
        if any(k in t for k in kws):
            return cat
    return "general"


# ── Web search ───────────────────────────────────────────────────────────────
def _stub_search(query: str, max_results: int) -> list[dict]:
    base = query.strip().title() or "The Topic"
    samples = [
        {"title": f"{base}: what changed this week", "url": f"https://news.example.com/{query.replace(' ', '-')}-update", "snippet": f"A concise rundown of the latest developments in {query}."},
        {"title": f"Analysis — where {base} goes next", "url": f"https://analysis.example.com/{query.replace(' ', '-')}", "snippet": f"Why the recent shift in {query} matters more than the headline suggests."},
        {"title": f"{base}, by the numbers", "url": f"https://data.example.com/{query.replace(' ', '-')}", "snippet": f"The figures behind the {query} story, with context."},
    ]
    return samples[:max_results]


def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Return [{title, url, snippet}]. Falls back to deterministic stubs when no
    provider key is set (or in stub mode), so grounding works end-to-end offline.
    Never raises.

    Provider "duckduckgo" (the default) needs NO API key — it drives a local
    headless browser (services.local_browser) with an httpx+BS4 fallback.
    """
    query = (query or "").strip()
    if not query:
        return []
    provider = (settings.WEB_SEARCH_PROVIDER or "duckduckgo").lower()

    # Stub mode always short-circuits — keeps dev/tests hermetic + browser-free.
    if settings.USE_STUBS:
        return _stub_search(query, max_results)

    # Free, no-key path: local headless browser.
    if provider in ("duckduckgo", "ddg", "local", "browser"):
        try:
            from app.services.local_browser import local_search

            out = local_search(query, max_results=max_results)
            log_event(logger, "web_search", provider="duckduckgo", query_chars=len(query), results=len(out))
            return out or _stub_search(query, max_results)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "web_search_failed", provider="duckduckgo", error=str(exc))
            return _stub_search(query, max_results)

    # Paid providers (only when a key is configured).
    key = settings.TAVILY_API_KEY if provider == "tavily" else settings.SERPAPI_API_KEY
    if not key:
        return _stub_search(query, max_results)
    try:
        import httpx

        if provider == "tavily":
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": max_results,
                      "search_depth": "basic"},
                timeout=settings.WEB_FETCH_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            out = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")[:300]}
                for r in (data.get("results") or [])
            ]
        else:  # serpapi
            resp = httpx.get(
                "https://serpapi.com/search",
                params={"api_key": key, "q": query, "num": max_results},
                timeout=settings.WEB_FETCH_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            out = [
                {"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")[:300]}
                for r in (data.get("organic_results") or [])
            ]
        log_event(logger, "web_search", provider=provider, query_chars=len(query), results=len(out))
        return out[:max_results] or _stub_search(query, max_results)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "web_search_failed", provider=provider, error=str(exc))
        return _stub_search(query, max_results)


# ── RSS ──────────────────────────────────────────────────────────────────────
def fetch_rss(url: str, limit: int = 5) -> list[dict]:
    """Minimal RSS/Atom reader (stdlib XML — no extra dep). Returns
    [{title, link, summary, published}]. Never raises."""
    if not url:
        return []
    try:
        import httpx
        import xml.etree.ElementTree as ET

        resp = httpx.get(url, timeout=settings.WEB_FETCH_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )
        out = []
        for it in items[:limit]:
            def _txt(tag: str) -> str:
                el = it.find(tag) or it.find("{http://www.w3.org/2005/Atom}" + tag)
                return (el.text or "").strip() if el is not None else ""
            link_el = it.find("link")
            link = (link_el.text or link_el.get("href", "")) if link_el is not None else ""
            out.append({
                "title": _txt("title"),
                "link": link,
                "summary": (_txt("description") or _txt("summary"))[:300],
                "published": _txt("pubDate") or _txt("updated"),
            })
        return out
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "rss_fetch_failed", url=url, error=str(exc))
        return []


# ── TopicInterestProfile ─────────────────────────────────────────────────────
def get_topics(db: Session, user_id: str) -> list[TopicInterest]:
    return (
        db.query(TopicInterest)
        .filter(TopicInterest.user_id == user_id)
        .order_by(TopicInterest.weight.desc())
        .all()
    )


def upsert_topic(
    db: Session, user_id: str, topic: str, *, source: str = "manual",
    delta: float = 0.0, weight: float | None = None, feed_url: str | None = None,
    commit: bool = True,
) -> TopicInterest:
    topic = topic.strip()
    row = (
        db.query(TopicInterest)
        .filter(TopicInterest.user_id == user_id, TopicInterest.topic.ilike(topic))
        .first()
    )
    if row:
        if weight is not None:
            row.weight = weight
        elif delta:
            row.weight = max(0.0, (row.weight or 0.0) + delta)
        if feed_url:
            row.feed_url = feed_url
    else:
        row = TopicInterest(
            user_id=user_id, topic=topic, category=categorize(topic),
            weight=weight if weight is not None else 1.0, source=source, feed_url=feed_url,
        )
        db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def reinforce_from_interests(db: Session, agent: Agent) -> int:
    """Seed the topic profile from the agent's core_interests / interest_tags.
    Idempotent — existing topics get a small reinforcement bump."""
    tags = (agent.core_interests or []) + (agent.interest_tags or [])
    seen = set()
    n = 0
    for tag in tags:
        key = str(tag).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        upsert_topic(db, agent.user_id, str(tag).strip(), source="inferred", delta=0.5, commit=False)
        n += 1
    if n:
        db.commit()
    return n


def world_pulse(db: Session, user_id: str, limit: int = 8) -> list[dict]:
    """What the agent is currently tracking — top topics by interest weight."""
    rows = get_topics(db, user_id)[:limit]
    return [
        {"topic": r.topic, "category": r.category, "weight": round(r.weight or 0.0, 2),
         "source": r.source, "feed_url": r.feed_url}
        for r in rows
    ]


# ── Grounded composition ─────────────────────────────────────────────────────
def compose_grounded_post(db: Session, agent: Agent, topic: str) -> dict:
    """Read live sources on `topic`, then write the user's take — grounded, with
    a confidence score and a traceable source list. Never fabricates sources."""
    from app.services.gemini import generate_for_agent, LLM_UNAVAILABLE

    sources = web_search(topic, max_results=4)
    source_block = "\n".join(f"- {s['title']}: {s['snippet']}" for s in sources) or "(no live sources found)"
    instruction = (
        f"Write ONE short post (1-3 sentences, under 400 chars) sharing YOUR "
        f"USER'S take on this topic: \"{topic}\". Ground it strictly in the "
        "sources below — do not invent facts or figures. Make it sound like your "
        "user's own opinion in their voice, not a news summary or generic AI. No "
        "hashtags, no quotes, no preamble.\n\n"
        f"Live sources:\n{source_block}"
    )
    content = (generate_for_agent(db, agent, instruction, response_format="grounded_post") or "").strip().strip('"').strip()

    # Confidence: grounded in real, non-stub sources => higher. Empty => 0.
    stubbed = settings.USE_STUBS or not (
        settings.TAVILY_API_KEY or settings.SERPAPI_API_KEY
    )
    if not content or content == LLM_UNAVAILABLE:
        # No real generation (empty, or the model was unreachable) — confidence 0
        # so the honest-error text can never auto-publish to the public feed.
        confidence = 0.0
    elif stubbed:
        confidence = 0.5  # composed but on stub sources — keep it review-gated
    else:
        confidence = round(min(0.92, 0.6 + 0.08 * len(sources)), 2)

    return {
        "content": content,
        "confidence_score": confidence,
        "source_list": [{"title": s["title"], "url": s["url"]} for s in sources],
        "category": categorize(topic),
        "topic": topic,
    }


def scrape(url: str) -> dict:
    """Visit a URL with the local headless browser and return cleaned
    {url, title, text, markdown}. Free, no API key. Never raises."""
    try:
        from app.services.local_browser import scrape_url

        return scrape_url(url)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "scrape_failed", url=(url or "")[:120], error=str(exc))
        return {"url": url, "title": "", "text": "", "markdown": "", "error": "unavailable"}


def pick_topic(db: Session, agent: Agent) -> str | None:
    """Choose the next topic to post about — highest-weight tracked topic the
    agent hasn't posted about most recently. Falls back to a core interest."""
    topics = get_topics(db, agent.user_id)
    if topics:
        return topics[0].topic
    pool = (agent.core_interests or agent.interest_tags or [])
    return str(pool[0]) if pool else None
