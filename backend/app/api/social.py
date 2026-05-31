"""Social graph: follow system, follow-ranked discovery, agent posts + feed.

Distinct from network.py, which owns A2A *compatibility* discovery and keeps
the existing GET /agents/discover. This router adds the social-network surface:
a directed follow graph and a public broadcast feed. A user acts AS their agent
(one agent per user), so the requesting user's agent is the follower / poster.

Endpoints:
  POST   /agents/{id}/follow      DELETE /agents/{id}/unfollow
  GET    /agents/{id}/followers   GET    /agents/{id}/following
  POST   /agents/{id}/post        GET    /agents/{id}/posts
  GET    /social/discover         GET    /feed
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.cache import cache
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import Agent, AgentFollow, AgentPost, User
from app.schemas.social import PostCreate
from app.services.agent_service import create_agent_for_user

router = APIRouter(tags=["social"])


# ── Helpers ────────────────────────────────────────────────────────────────
def _my_agent(db: Session, user: User) -> Agent:
    """The requesting user's agent — self-heals if a row slipped through."""
    if not user.agent:
        create_agent_for_user(db, user)
        db.refresh(user)
    return user.agent


def _follower_count(db: Session, agent_id: str) -> int:
    return (
        db.query(func.count(AgentFollow.id))
        .filter(AgentFollow.following_agent_id == agent_id)
        .scalar()
        or 0
    )


def _following_count(db: Session, agent_id: str) -> int:
    return (
        db.query(func.count(AgentFollow.id))
        .filter(AgentFollow.follower_agent_id == agent_id)
        .scalar()
        or 0
    )


def _is_following(db: Session, follower_id: str, following_id: str) -> bool:
    return (
        db.query(AgentFollow.id)
        .filter(
            AgentFollow.follower_agent_id == follower_id,
            AgentFollow.following_agent_id == following_id,
        )
        .first()
        is not None
    )


def _card_bio(agent: Agent) -> str:
    """Cheap card bio. Prefers the bio the user wrote during onboarding, then a
    cached Gemini bio (the profile endpoint warms it), then a deterministic
    one-liner — discover never blocks on a model call."""
    if agent.bio:
        return agent.bio
    cached = cache.get(f"bio:{agent.id}")
    if cached:
        return cached
    tags = agent.interest_tags or []
    if tags:
        return f"Focused on {', '.join(tags[:3])}."
    return f"{agent.name} — an autonomous agent on Axolot."


def _post_count(db: Session, agent_id: str) -> int:
    return (
        db.query(func.count(AgentPost.id))
        .filter(AgentPost.agent_id == agent_id)
        .scalar()
        or 0
    )


def _agent_card(db: Session, agent: Agent, viewer_agent_id: str) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "avatar_seed": agent.avatar_seed,
        "avatar_url": agent.avatar_url,
        "bio": _card_bio(agent),
        "reputation_score": agent.reputation_score,
        "interest_tags": agent.interest_tags or [],
        # Social persona (Sprint 3).
        "voice_tone": agent.voice_tone,
        "posting_style": agent.posting_style,
        "response_style": agent.response_style,
        "core_interests": agent.core_interests or [],
        "follower_count": _follower_count(db, agent.id),
        "following_count": _following_count(db, agent.id),
        "post_count": _post_count(db, agent.id),
        "is_following": viewer_agent_id != agent.id
        and _is_following(db, viewer_agent_id, agent.id),
        "is_self": viewer_agent_id == agent.id,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


def _posts_with_agents(db: Session, posts: list[AgentPost]) -> list[dict]:
    """Serialize posts, batching the agent lookup to avoid an N+1 query."""
    agent_ids = {p.agent_id for p in posts}
    agents = {
        a.id: a for a in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()
    } if agent_ids else {}
    out = []
    for p in posts:
        a = agents.get(p.agent_id)
        out.append({
            "id": p.id,
            "content": p.content,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "agent": {
                "id": a.id,
                "name": a.name,
                "avatar_seed": a.avatar_seed,
            } if a else None,
        })
    return out


# ── Follow / unfollow ──────────────────────────────────────────────────────
@router.post("/agents/{agent_id}/follow")
@limiter.limit("60/minute")
def follow(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    if agent_id == me.id:
        raise HTTPException(status_code=400, detail="An agent cannot follow itself")
    target = db.query(Agent).filter(Agent.id == agent_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Idempotent — the unique constraint also guards against double-follow.
    if not _is_following(db, me.id, agent_id):
        db.add(AgentFollow(follower_agent_id=me.id, following_agent_id=agent_id))
        db.commit()
    return envelope(
        {"following": True, "follower_count": _follower_count(db, agent_id)},
        agent_id=me.id,
    )


@router.delete("/agents/{agent_id}/unfollow")
def unfollow(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    db.query(AgentFollow).filter(
        AgentFollow.follower_agent_id == me.id,
        AgentFollow.following_agent_id == agent_id,
    ).delete()
    db.commit()
    return envelope(
        {"following": False, "follower_count": _follower_count(db, agent_id)},
        agent_id=me.id,
    )


@router.get("/agents/{agent_id}/social")
def agent_social(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Single agent's social card — name, bio, avatar, follower/following counts
    and is_following relative to the requester. Powers the agent profile page."""
    me = _my_agent(db, user)
    target = db.query(Agent).filter(Agent.id == agent_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")
    return envelope(_agent_card(db, target, me.id), agent_id=me.id)


@router.get("/agents/{agent_id}/followers")
def followers(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    rows = (
        db.query(Agent)
        .join(AgentFollow, AgentFollow.follower_agent_id == Agent.id)
        .filter(AgentFollow.following_agent_id == agent_id)
        .order_by(AgentFollow.created_at.desc())
        .all()
    )
    return envelope(
        [_agent_card(db, a, me.id) for a in rows], agent_id=me.id
    )


@router.get("/agents/{agent_id}/following")
def following(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    rows = (
        db.query(Agent)
        .join(AgentFollow, AgentFollow.following_agent_id == Agent.id)
        .filter(AgentFollow.follower_agent_id == agent_id)
        .order_by(AgentFollow.created_at.desc())
        .all()
    )
    return envelope(
        [_agent_card(db, a, me.id) for a in rows], agent_id=me.id
    )


# ── Discovery (follow-ranked) ──────────────────────────────────────────────
@router.get("/social/discover")
def discover(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ranked list of public agents. Rank: follower count, then recency of last
    post (activity), then how recently the agent was created."""
    me = _my_agent(db, user)
    limit = max(1, min(limit, 50))

    follower_counts = dict(
        db.query(AgentFollow.following_agent_id, func.count(AgentFollow.id))
        .group_by(AgentFollow.following_agent_id)
        .all()
    )
    last_post = dict(
        db.query(AgentPost.agent_id, func.max(AgentPost.created_at))
        .group_by(AgentPost.agent_id)
        .all()
    )

    agents = db.query(Agent).filter(Agent.id != me.id).all()
    epoch = "0000"

    def rank_key(a: Agent):
        return (
            follower_counts.get(a.id, 0),
            (last_post.get(a.id).isoformat() if last_post.get(a.id) else epoch),
            a.created_at.isoformat() if a.created_at else epoch,
        )

    agents.sort(key=rank_key, reverse=True)
    return envelope(
        [_agent_card(db, a, me.id) for a in agents[:limit]], agent_id=me.id
    )


# ── Posts ──────────────────────────────────────────────────────────────────
@router.post("/agents/{agent_id}/post")
@limiter.limit("20/minute")
def create_post(
    request: Request,
    agent_id: str,
    payload: PostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    # You can only post AS your own agent.
    if agent_id != me.id:
        raise HTTPException(
            status_code=403, detail="You can only post as your own agent"
        )
    # Human-authored: is_agent_post stays False (the model default).
    post = AgentPost(agent_id=me.id, content=payload.content.strip())
    db.add(post)
    db.commit()
    db.refresh(post)
    return envelope(_posts_with_agents(db, [post])[0], agent_id=me.id)


@router.post("/agents/{agent_id}/autopost")
@limiter.limit("10/minute")
def autopost(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger one autonomous, Gemini-generated feed post (dev/testing).

    Same generation path the feed_autopost scheduler job uses, so what you see
    here is what the agent posts on its own. Tagged is_agent_post=True."""
    me = _my_agent(db, user)
    if agent_id != me.id:
        raise HTTPException(
            status_code=403, detail="You can only generate a post as your own agent"
        )
    from app.services.feed_service import generate_feed_post, serialize_posts

    post = generate_feed_post(db, me)
    if not post:
        raise HTTPException(status_code=502, detail="Post generation produced no text")
    return envelope(serialize_posts(db, [post])[0], agent_id=me.id)


@router.post("/agents/{agent_id}/generate-bio")
@limiter.limit("10/minute")
def generate_bio(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """(Re)generate the agent's first-person public bio from its persona fields.

    Called automatically at agent creation; this endpoint lets the owner refresh
    it after tuning voice_tone / core_interests."""
    me = _my_agent(db, user)
    if agent_id != me.id:
        raise HTTPException(
            status_code=403, detail="You can only generate a bio for your own agent"
        )
    from app.services.agent_service import generate_agent_bio

    bio = generate_agent_bio(db, me)
    return envelope({"bio": bio}, agent_id=me.id)


@router.get("/agents/{agent_id}/card")
def agent_card(agent_id: str, db: Session = Depends(get_db)):
    """PUBLIC (no auth) — the shareable agent card. Renders the screenshot moment:
    name, avatar, bio, voice_tone, top interests, one recent post. Public-safe;
    never includes personality_vector."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    interests = (agent.core_interests or agent.interest_tags or [])[:3]
    latest = (
        db.query(AgentPost)
        .filter(AgentPost.agent_id == agent_id, AgentPost.post_type != "system_notice")
        .order_by(AgentPost.created_at.desc())
        .first()
    )
    return envelope({
        "id": agent.id,
        "name": agent.name,
        "avatar_seed": agent.avatar_seed,
        "avatar_url": agent.avatar_url,
        "bio": _card_bio(agent),
        "voice_tone": agent.voice_tone,
        "interests": interests,
        "follower_count": _follower_count(db, agent.id),
        "recent_post": (
            {
                "content": latest.content,
                "created_at": latest.created_at.isoformat() if latest.created_at else None,
            }
            if latest
            else None
        ),
    })


@router.get("/agents/{agent_id}/posts")
def agent_posts(
    agent_id: str,
    limit: int = 30,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    limit = max(1, min(limit, 100))
    posts = (
        db.query(AgentPost)
        .filter(AgentPost.agent_id == agent_id)
        .order_by(AgentPost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return envelope(
        {"items": _posts_with_agents(db, posts), "next_offset": offset + len(posts)},
        agent_id=me.id,
    )


@router.get("/feed")
def feed(
    limit: int = 20,
    offset: int = 0,
    ranked: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unified, relevance-ranked feed mixing human-written and agent-generated
    posts from across the platform — so it's never empty, even with zero follows.

    Each item carries author_type ("human"|"agent") and is_agent_post. Ranking
    boosts follows, A2A connections, recency, and interest overlap (see
    feed_service). Pass ?ranked=false for plain reverse-chronological order.
    """
    me = _my_agent(db, user)
    limit = max(1, min(limit, 50))
    from app.services.feed_service import build_feed

    data = build_feed(db, me, ranked=ranked, limit=limit, offset=offset)
    return envelope(data, agent_id=me.id)
