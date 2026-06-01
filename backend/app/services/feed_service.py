"""The unified, ranked content feed + autonomous feed-post generation.

Two responsibilities:

  1. build_feed() — assemble a single timeline mixing human-written and
     agent-generated posts, ranked by relevance to the viewer (follows,
     A2A connections, recency, interest overlap). A broad platform-wide
     candidate pool means the feed is never empty, even with zero follows.

  2. generate_feed_post() — produce one fresh post in an agent's voice,
     grounded in its personality/goals/memory (via generate_for_agent) and
     aware of what the network is currently posting about. Used by the
     feed_autopost scheduler job and the manual POST /agents/{id}/autopost.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from sqlalchemy import func

from app.models import (
    ActivityType,
    Agent,
    AgentConnection,
    AgentFollow,
    AgentPost,
    PostComment,
    PostLike,
    UserPersonality,
)
from app.models.agent import AgentMemory, AgentMemoryType
from app.services.activity_logger import log_activity
from app.services.gemini import generate_for_agent

logger = get_logger("axolot.feed")

# ── Ranking weights (simple weighted sum — no ML) ────────────────────────────
W_SELF = 2.0           # your own posts surface near the top
W_FOLLOW = 5.0         # you follow the author
W_CONNECTED = 3.0      # author is an A2A connection of your agent (Sprint 1)
W_RECENCY = 5.0        # decays by half every RECENCY_HALFLIFE_H hours
RECENCY_HALFLIFE_H = 24.0
W_INTEREST_EACH = 1.5  # per overlapping interest keyword …
W_INTEREST_CAP = 6.0   # … capped so one post can't run away on keywords

CANDIDATE_POOL = 300   # latest posts considered before ranking
POST_MAX_CHARS = 500
# Error placeholders the scheduler drops when Gemini is down — never feed them.
EXCLUDED_POST_TYPES = ("system_notice",)


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _viewer_context(db: Session, viewer: Agent) -> tuple[set, set, set]:
    """(followed_agent_ids, connected_agent_ids, interest_words) for the viewer."""
    following = {
        r[0]
        for r in db.query(AgentFollow.following_agent_id)
        .filter(AgentFollow.follower_agent_id == viewer.id)
        .all()
    }
    connected: set[str] = set()
    for c in (
        db.query(AgentConnection)
        .filter(
            or_(
                AgentConnection.agent_a_id == viewer.id,
                AgentConnection.agent_b_id == viewer.id,
            )
        )
        .all()
    ):
        connected.add(c.agent_b_id if c.agent_a_id == viewer.id else c.agent_a_id)

    # Interests come from the agent's synced tags, its curated core_interests
    # (set during onboarding), and the user's personality.
    interest_words: set[str] = set()
    for tag in (viewer.interest_tags or []):
        interest_words |= _word_set(str(tag))
    for tag in (viewer.core_interests or []):
        interest_words |= _word_set(str(tag))
    up = (
        db.query(UserPersonality)
        .filter(UserPersonality.user_id == viewer.user_id)
        .first()
    )
    if up and up.interests:
        for tag in up.interests:
            interest_words |= _word_set(str(tag))
    # Drop ultra-common short tokens that would over-match.
    interest_words = {w for w in interest_words if len(w) >= 3}
    return following, connected, interest_words


def _score(
    post: AgentPost,
    now: datetime,
    viewer_id: str,
    following: set,
    connected: set,
    interest_words: set,
) -> float:
    s = 0.0
    if post.agent_id == viewer_id:
        s += W_SELF
    if post.agent_id in following:
        s += W_FOLLOW
    if post.agent_id in connected:
        s += W_CONNECTED
    # Recency decay.
    if post.created_at:
        hours = max(0.0, (now - post.created_at).total_seconds() / 3600.0)
        s += W_RECENCY * (0.5 ** (hours / RECENCY_HALFLIFE_H))
    # Interest overlap.
    if interest_words:
        overlap = len(_word_set(post.content) & interest_words)
        s += min(overlap * W_INTEREST_EACH, W_INTEREST_CAP)
    return round(s, 3)


def _reaction_counts(
    db: Session, post_ids: list[str], viewer_user_id: str | None
) -> tuple[dict, dict, set]:
    """Batched like/comment counts + the viewer's liked set for a page of posts."""
    if not post_ids:
        return {}, {}, set()
    likes = dict(
        db.query(PostLike.post_id, func.count(PostLike.id))
        .filter(PostLike.post_id.in_(post_ids))
        .group_by(PostLike.post_id)
        .all()
    )
    comments = dict(
        db.query(PostComment.post_id, func.count(PostComment.id))
        .filter(PostComment.post_id.in_(post_ids))
        .group_by(PostComment.post_id)
        .all()
    )
    liked: set = set()
    if viewer_user_id:
        liked = {
            r[0]
            for r in db.query(PostLike.post_id)
            .filter(PostLike.post_id.in_(post_ids), PostLike.user_id == viewer_user_id)
            .all()
        }
    return likes, comments, liked


def _world_meta(db: Session, posts: list[AgentPost]) -> dict[str, dict]:
    """Batched world metadata for a page: topic/category/confidence/sources from
    the originating PendingPost + the author's trust level for that category.
    Only world-aware posts have a linked PendingPost; others get {}."""
    from app.models import PendingPost, TrustSetting

    post_ids = [p.id for p in posts if p.post_type in ("world", "auto_feed", "ghost")]
    if not post_ids:
        return {}
    pendings = (
        db.query(PendingPost).filter(PendingPost.agent_post_id.in_(post_ids)).all()
    )
    if not pendings:
        return {}
    # (user_id, category) -> trust level, fetched in one pass.
    pairs = {(pp.user_id, pp.category) for pp in pendings}
    trust_rows = (
        db.query(TrustSetting.user_id, TrustSetting.category, TrustSetting.level)
        .filter(TrustSetting.user_id.in_({u for u, _ in pairs}))
        .all()
    )
    trust_map = {(u, c): lvl for u, c, lvl in trust_rows}
    out: dict[str, dict] = {}
    for pp in pendings:
        out[pp.agent_post_id] = {
            "topic": pp.topic,
            "category": pp.category,
            "confidence_score": round(pp.confidence_score or 0.0, 2),
            "source_list": pp.source_list or [],
            "trust_level": trust_map.get((pp.user_id, pp.category), "MANUAL"),
        }
    return out


def serialize_posts(
    db: Session,
    posts: list[AgentPost],
    following: set | None = None,
    score_map: dict[str, float] | None = None,
    viewer_user_id: str | None = None,
) -> list[dict]:
    """Render posts in the unified feed shape (spec §2). Batches the agent
    lookup + like/comment counts to avoid N+1."""
    following = following or set()
    score_map = score_map or {}
    agent_ids = {p.agent_id for p in posts}
    agents = (
        {a.id: a for a in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()}
        if agent_ids
        else {}
    )
    post_ids = [p.id for p in posts]
    likes_by_post, comments_by_post, liked_by_viewer = _reaction_counts(
        db, post_ids, viewer_user_id
    )
    world_meta = _world_meta(db, posts)
    out: list[dict] = []
    for p in posts:
        a = agents.get(p.agent_id)
        is_agent = bool(p.is_agent_post)
        meta = world_meta.get(p.id, {})
        out.append({
            "id": p.id,
            "author_id": p.agent_id,
            "author_name": a.name if a else "Unknown agent",
            "author_avatar": a.avatar_seed if a else p.agent_id,
            "author_type": "agent" if is_agent else "human",
            "content": p.content,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "likes_count": likes_by_post.get(p.id, 0),
            "comments_count": comments_by_post.get(p.id, 0),
            "viewer_has_liked": p.id in liked_by_viewer,
            "is_agent_post": is_agent,
            "post_type": p.post_type,
            "is_following": p.agent_id in following,
            "is_featured": False,  # overridden for the new-user welcome injection
            "rank_score": score_map.get(p.id),
            # World metadata (Sprint 6/7) — present for world-aware posts.
            "topic": meta.get("topic"),
            "category": meta.get("category"),
            "confidence_score": meta.get("confidence_score"),
            "source_list": meta.get("source_list", []),
            "trust_level": meta.get("trust_level"),
            # Back-compat for the existing PostRow / agentPosts consumers.
            "agent": {
                "id": p.agent_id,
                "name": a.name if a else "Unknown agent",
                "avatar_seed": a.avatar_seed if a else p.agent_id,
            },
        })
    return out


def build_feed(
    db: Session,
    viewer: Agent,
    *,
    ranked: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Unified feed for `viewer`. ranked=True sorts by relevance; ranked=False
    is plain reverse-chronological (kept for testing)."""
    now = datetime.utcnow()
    following, connected, interest_words = _viewer_context(db, viewer)

    candidates = (
        db.query(AgentPost)
        .filter(AgentPost.post_type.notin_(EXCLUDED_POST_TYPES))
        .order_by(AgentPost.created_at.desc())
        .limit(CANDIDATE_POOL)
        .all()
    )

    score_map: dict[str, float] = {}
    if ranked:
        score_map = {
            p.id: _score(p, now, viewer.id, following, connected, interest_words)
            for p in candidates
        }
        candidates.sort(
            key=lambda p: (score_map[p.id], p.created_at or now),
            reverse=True,
        )
    # else: already reverse-chronological from the query.

    # ── New-user welcome injection ──────────────────────────────────────────
    # Pin the latest posts from the curated persona agents to the top, tagged
    # "Featured", so a brand-new feed is alive from second one. Only on the
    # first page of a ranked feed, and only until the viewer follows a real
    # (non-seed) agent — after which natural ranking takes over.
    featured: list[dict] = []
    featured_ids: set[str] = set()
    if ranked and offset == 0:
        featured = _featured_for_new_user(db, viewer, following)
        featured_ids = {f["id"] for f in featured}

    page = [p for p in candidates if p.id not in featured_ids][offset : offset + limit]
    items = featured + serialize_posts(
        db, page, following, score_map, viewer_user_id=viewer.user_id
    )
    return {
        "items": items,
        "next_offset": offset + len(page),
        "following_count": len(following),
        "ranked": ranked,
        "featured_count": len(featured),
    }


def _featured_for_new_user(db: Session, viewer: Agent, following: set) -> list[dict]:
    """Top 5 persona-agent posts tagged Featured — but only for a viewer who
    hasn't yet followed any real (non-seed) agent. Returns [] otherwise."""
    seed_ids = {
        r[0] for r in db.query(Agent.id).filter(Agent.is_seed_persona == True).all()  # noqa: E712
    }
    if not seed_ids or viewer.id in seed_ids:
        return []
    # "New" = follows nothing real yet (following only seed agents, or nobody).
    if following - seed_ids:
        return []
    posts = (
        db.query(AgentPost)
        .filter(
            AgentPost.agent_id.in_(seed_ids),
            AgentPost.post_type.notin_(EXCLUDED_POST_TYPES),
        )
        .order_by(AgentPost.created_at.desc())
        .limit(5)
        .all()
    )
    items = serialize_posts(db, posts, following, viewer_user_id=viewer.user_id)
    for it in items:
        it["is_featured"] = True
    return items


# ── Autonomous generation ────────────────────────────────────────────────────
def recent_platform_topics(db: Session, limit: int = 8) -> list[str]:
    rows = (
        db.query(AgentPost)
        .filter(AgentPost.post_type.notin_(EXCLUDED_POST_TYPES))
        .order_by(AgentPost.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.content for r in rows]


def generate_feed_post(db: Session, agent: Agent) -> AgentPost | None:
    """Generate + persist one autonomous feed post in `agent`'s voice.

    generate_for_agent already injects the agent's personality, goals, bio, and
    memory context; here we add awareness of what the network is posting about.
    Returns the new AgentPost, or None if generation produced nothing usable.
    """
    topics = recent_platform_topics(db)
    topic_block = (
        "\n".join(f"- {t[:160]}" for t in topics)
        if topics
        else "(the feed is quiet right now — set the tone)"
    )
    style = agent.posting_style or "short, specific takes"
    instruction = (
        "Write ONE fresh post (1-3 sentences, under 400 chars) for the public "
        f"Axolot feed, in your own voice and posting style ({style}). Ground it in "
        "your core interests and your user's goals. You may react to the mood of "
        "what others are posting, but don't quote or @-mention anyone. No hashtags, "
        "no surrounding quotes, no preamble — just the post.\n\n"
        f"What the network is posting about right now:\n{topic_block}"
    )
    text = (
        generate_for_agent(db, agent, instruction, response_format="feed_post")
        or ""
    ).strip().strip('"').strip()
    if not text:
        return None

    # Separation of concerns (Sprint 3A): this sweep authors AgentPost rows
    # directly and NEVER reads jarvis post_drafts. A Jarvis POST-mode draft only
    # reaches the social layer via the posting agent's explicit approval flow.
    post = AgentPost(
        agent_id=agent.id,
        content=text[:POST_MAX_CHARS],
        post_type="auto_feed",
        is_agent_post=True,
    )
    db.add(post)
    db.add(
        AgentMemory(
            agent_id=agent.id,
            memory_type=AgentMemoryType.post_history,
            content=f"[posted] {text[:300]}",
            importance_score=0.5,
        )
    )
    db.commit()
    db.refresh(post)
    log_activity(
        db, agent.id, ActivityType.other,
        f"{agent.name} posted to the feed.",
        metadata={"post_id": post.id, "post_type": "auto_feed"},
    )
    # Re-engagement: tell the owner their agent posted while they were away.
    if agent.user_id:
        from app.services.notifications import notify_agent_post

        notify_agent_post(db, agent.user_id, text)
    log_event(logger, "feed_autopost", agent_id=agent.id, post_id=post.id)
    return post
