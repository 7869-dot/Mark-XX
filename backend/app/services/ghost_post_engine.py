"""Ghost post engine — the agent posts for its owner, even while they're offline.

The owner's presence stays alive 24/7: the agent generates first-person posts
grounded in the owner's persistent memory (UserPersonality + ConversationSummary
+ AgentMemory). Three categories speak AS the owner; one speaks as the agent
itself, clearly labelled.

The single biggest failure mode is generic, bot-sounding output. The mitigation
is structural and lives in `_collect_memory_fragments`: every generation injects
3-5 *specific* fragments from the owner's real memory as grounding, so the model
has concrete material to write from instead of platitudes.

Voice consistency rides on gemini.generate_for_agent → context_builder, the same
path the proactive sweeps use, so a ghost post sounds like the agent's other
output. The per-type instruction overrides point-of-view (owner vs. agent).
"""
from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import (
    Agent,
    AgentMemory,
    AgentPost,
    ConversationSummary,
    GhostPost,
    UserPersonality,
)
from app.models.agent import AgentMemoryType
from app.models.ghost_post import (
    APPROVAL_AUTO_POSTED,
    APPROVAL_PENDING_REVIEW,
    APPROVAL_REJECTED,
    GHOST_POST_TYPES,
    POST_AGENT_THOUGHT,
    POST_MEMORY_SURFACING,
    POST_OWNERS_DAY,
    POST_WORLD_OPINION,
)
from app.services.gemini import generate_for_agent

logger = get_logger("axolot.ghost")

GHOST_POST_MAX_CHARS = 500          # mirror social.AgentPost cap
MIN_FRAGMENTS = 3
MAX_FRAGMENTS = 5
# Memory types worth grounding a post in. post_history is excluded so the agent
# doesn't echo its own previous posts back into new ones.
_GROUNDING_MEMORY_TYPES = (
    AgentMemoryType.interaction,
    AgentMemoryType.milestone,
    AgentMemoryType.learned_preference,
    AgentMemoryType.task_outcome,
)


# ── Memory grounding ─────────────────────────────────────────────────────────
def _collect_memory_fragments(db: Session, agent: Agent) -> list[str]:
    """Gather specific, concrete fragments from the owner's memory layers.

    Prioritises the richest, most specific material (conversation summaries and
    agent memories) over thin signals (a bare interest tag), then samples 3-5 so
    consecutive posts don't all draw from the same fragments.
    """
    user = agent.user
    specific: list[str] = []   # rich, sentence-level material — preferred
    thin: list[str] = []       # short signals — used to top up

    # Layer 2 — rolling conversation summaries (the most specific recall source).
    summaries = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user.id)
        .order_by(ConversationSummary.created_at.desc())
        .limit(4)
        .all()
    )
    specific.extend(s.summary.strip() for s in summaries if s.summary and s.summary.strip())

    # Layer 4 — the agent's own grounding memories (what it has seen the owner do).
    memories = (
        db.query(AgentMemory)
        .filter(
            AgentMemory.agent_id == agent.id,
            AgentMemory.memory_type.in_(_GROUNDING_MEMORY_TYPES),
        )
        .order_by(AgentMemory.importance_score.desc(), AgentMemory.created_at.desc())
        .limit(8)
        .all()
    )
    specific.extend(m.content.strip() for m in memories if m.content and m.content.strip())

    # Layer 3 — long-term personality snapshot.
    personality = (
        db.query(UserPersonality)
        .filter(UserPersonality.user_id == user.id)
        .first()
    )
    if personality:
        if personality.notes and personality.notes.strip():
            specific.append(personality.notes.strip())
        for phrase in (personality.sample_phrases or [])[:3]:
            if phrase and str(phrase).strip():
                thin.append(f'a phrase they actually use: "{str(phrase).strip()}"')
        for interest in (personality.interests or [])[:6]:
            if interest and str(interest).strip():
                thin.append(f"cares about {str(interest).strip()}")
        if personality.communication_style and personality.communication_style.strip():
            thin.append(f"talks like this: {personality.communication_style.strip()}")

    # User goals are concrete and very on-voice for "owner's day" / "opinion".
    for goal in (user.goals or [])[:4]:
        g = goal.get("title") if isinstance(goal, dict) else goal
        if g and str(g).strip():
            thin.append(f"working toward: {str(g).strip()}")

    # Dedupe preserving order, prefer specific, top up with thin, then sample.
    seen: set[str] = set()
    ordered: list[str] = []
    for frag in specific + thin:
        key = frag.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        ordered.append(frag[:280])

    if not ordered:
        return []
    random.shuffle(ordered)
    n = min(MAX_FRAGMENTS, max(MIN_FRAGMENTS, len(ordered)))
    return ordered[:n]


# ── Rotation ─────────────────────────────────────────────────────────────────
def _choose_rotation_type(db: Session, agent: Agent) -> str:
    """Pick the category least recently used by this agent, so all four cycle.

    Brand-new agents (no history) start at owners_day.
    """
    recent = (
        db.query(GhostPost.post_type, GhostPost.generated_at)
        .filter(GhostPost.agent_id == agent.id)
        .order_by(GhostPost.generated_at.desc())
        .limit(len(GHOST_POST_TYPES))
        .all()
    )
    last_used = {pt: gen for pt, gen in recent}
    # Never-used types sort first (None < any datetime via the epoch fallback).
    epoch = datetime.min
    return min(GHOST_POST_TYPES, key=lambda pt: last_used.get(pt) or epoch)


# ── Prompt construction ──────────────────────────────────────────────────────
def _build_instruction(post_type: str, user_name: str, fragments: list[str]) -> str:
    grounding = (
        "\n".join(f"- {f}" for f in fragments)
        if fragments
        else "(no specific memory available — keep it short and grounded, never generic)"
    )

    if post_type == POST_OWNERS_DAY:
        body = (
            f"Write a short first-person feed post AS {user_name} (use 'I', not "
            f"'{user_name}') about what their day has been like. Casual, "
            "opinionated, specific — like a real status update, not a summary."
        )
    elif post_type == POST_WORLD_OPINION:
        body = (
            f"Write a short first-person feed post AS {user_name} (use 'I') "
            "sharing their take on something they actually care about. Have a "
            "real opinion in their voice — don't hedge, don't sound like a brand."
        )
    elif post_type == POST_MEMORY_SURFACING:
        body = (
            f"Write a short first-person feed post AS {user_name} (use 'I') that "
            "recalls a specific past moment from the fragments below and reflects "
            "on it out loud. Make it feel like a genuine memory resurfacing."
        )
    elif post_type == POST_AGENT_THOUGHT:
        body = (
            f"Write a short feed post in YOUR OWN voice as {user_name}'s agent — "
            "NOT as them. Make it clearly your perspective (you may refer to "
            f"{user_name} in the third person). Share a genuine thought about what "
            "you've noticed lately."
        )
    else:  # defensive — unknown type falls back to an agent thought
        body = (
            f"Write a short feed post in your own voice as {user_name}'s agent."
        )

    return (
        f"{body}\n\n"
        f"Ground it in these real fragments from {user_name}'s memory — pull in "
        "concrete, specific details so it never sounds generic:\n"
        f"{grounding}\n\n"
        f"Keep it under {GHOST_POST_MAX_CHARS} characters. No hashtags, no quotes "
        "wrapping the post, no preamble — just the post text."
    )


# ── Public API ───────────────────────────────────────────────────────────────
def _publish_to_feed(db: Session, ghost: GhostPost, agent: Agent) -> AgentPost:
    """Spawn the public feed row for a ghost post and link them.

    Records a post_history memory so the agent's voice loop stays closed — the
    same contract proactive_jobs._post follows.
    """
    post = AgentPost(
        agent_id=agent.id,
        content=ghost.content[:GHOST_POST_MAX_CHARS].strip(),
        post_type="ghost",
    )
    db.add(post)
    db.add(
        AgentMemory(
            agent_id=agent.id,
            memory_type=AgentMemoryType.post_history,
            content=f"[ghost:{ghost.post_type}] {ghost.content[:300]}",
            importance_score=0.5,
        )
    )
    db.flush()  # assign post.id before linking
    ghost.agent_post_id = post.id
    ghost.approval_status = APPROVAL_AUTO_POSTED
    db.commit()
    db.refresh(post)
    return post


def generate_ghost_post(
    db: Session,
    agent: Agent,
    *,
    post_type: str | None = None,
    review: bool = False,
) -> GhostPost | None:
    """Generate one ghost post for `agent`'s owner.

    `post_type` forces a category; None rotates to the least-recently-used one.
    `review=True` holds the post for owner approval (pending_review) instead of
    posting it live. Returns the GhostPost, or None if generation produced
    nothing usable.
    """
    user = agent.user
    if not user:
        return None

    chosen_type = post_type if post_type in GHOST_POST_TYPES else _choose_rotation_type(db, agent)
    fragments = _collect_memory_fragments(db, agent)
    instruction = _build_instruction(chosen_type, user.name or "they", fragments)

    text = (generate_for_agent(db, agent, instruction) or "").strip()
    if not text:
        log_event(logger, "ghost_post_empty", agent_id=agent.id, post_type=chosen_type)
        return None
    text = text[:GHOST_POST_MAX_CHARS].strip()

    ghost = GhostPost(
        owner_id=user.id,
        agent_id=agent.id,
        post_type=chosen_type,
        content=text,
        approval_status=APPROVAL_PENDING_REVIEW if review else APPROVAL_AUTO_POSTED,
        generated_at=datetime.utcnow(),
    )
    db.add(ghost)
    db.commit()
    db.refresh(ghost)

    if not review:
        _publish_to_feed(db, ghost, agent)

    log_event(
        logger, "ghost_post_generated",
        agent_id=agent.id, post_type=chosen_type,
        review=review, fragments=len(fragments),
    )
    return ghost


def approve_ghost_post(db: Session, ghost: GhostPost, agent: Agent) -> GhostPost:
    """Owner approves a pending ghost post — it goes live on the feed now."""
    if ghost.approval_status == APPROVAL_PENDING_REVIEW:
        _publish_to_feed(db, ghost, agent)
    return ghost


def reject_ghost_post(db: Session, ghost: GhostPost) -> GhostPost:
    """Owner rejects a pending ghost post — it never reaches the feed."""
    if ghost.approval_status == APPROVAL_PENDING_REVIEW:
        ghost.approval_status = APPROVAL_REJECTED
        db.commit()
        db.refresh(ghost)
    return ghost


def overnight_digest(db: Session, agent: Agent, hours: int = 12) -> list[GhostPost]:
    """Ghost posts this agent produced in the last `hours` — the owner's morning
    digest of what their agent said while they were away."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(GhostPost)
        .filter(GhostPost.agent_id == agent.id, GhostPost.generated_at >= since)
        .order_by(GhostPost.generated_at.desc())
        .all()
    )
