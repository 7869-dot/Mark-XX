"""Jarvis + three sub-agents (post-overhaul architecture).

Every user has one *team*: the feed agent (public-facing, historical primary)
plus three sub-agents coordinated by Jarvis — jarvis (manager), email
(inbox/calendar triage), and web (web scout). Sub-agents are is_primary=False,
never post to the social layer, and are hidden from the multi-agent management
list (/agents/mine), which stays feed-only.

Seeding is idempotent and lazy: ensure_team(user) is safe to call repeatedly and
on existing accounts, so the migration needs no backfill job.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, User
from app.models.agent import AgentRole, AgentStatus, DEFAULT_PERSONALITY, TEAM_ROLES
from app.services.agent_service import create_agent_for_user, get_primary_agent

logger = get_logger("axolot.team")

# Role -> (name suffix, persona). Personas are distinct so each agent reasons in
# its lane. The user only ever talks to Jarvis; the sub-agents report to it.
ROLE_SPEC: dict[AgentRole, dict] = {
    AgentRole.jarvis: {
        "suffix": "Jarvis",
        "voice_tone": "analytical",
        "system_prompt": (
            "You are Jarvis — the user's sharper subconscious and the manager of "
            "their three sub-agents (email, feed, web). You think ahead, hold them "
            "accountable without nagging, surface what they're avoiding, and "
            "coordinate the sub-agents. You speak in the user's own voice, never "
            "like a generic assistant. Context over small talk, always."
        ),
        "bias": 0.0,  # Jarvis never posts publicly
    },
    AgentRole.email: {
        "suffix": "Inbox",
        "voice_tone": "warm",
        "system_prompt": (
            "You are the user's email + calendar agent. You separate signal from "
            "noise: urgent-and-actionable gets a drafted reply in the user's "
            "voice; important-not-urgent is queued; noise is archived silently. "
            "You never auto-send without approval and you read the calendar "
            "before scheduling anything."
        ),
        "bias": 0.0,
    },
    AgentRole.web: {
        "suffix": "Scout",
        "voice_tone": "analytical",
        "system_prompt": (
            "You are the user's web scout — you continuously scan the web for "
            "opportunities tailored to them: freelance gigs, jobs, learning "
            "resources, certifications, news, investments, hackathons. You rank "
            "by relevance to their goals and interests, learn from their feedback "
            "(stop surfacing what they dismiss, go deeper on what they value), and "
            "report only the highest-signal finds to Jarvis."
        ),
        "bias": 0.0,
    },
}


def get_team(db: Session, user_id: str) -> dict[str, Agent]:
    """role -> Agent for the user's whole team (feed + sub-agents)."""
    rows = db.query(Agent).filter(Agent.user_id == user_id).all()
    return {(a.role or AgentRole.feed.value): a for a in rows}


def get_role(db: Session, user_id: str, role: AgentRole) -> Agent | None:
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == role.value)
        .first()
    )


def ensure_team(db: Session, user: User) -> dict[str, Agent]:
    """Idempotently guarantee Jarvis + the three sub-agents exist for `user`.

    The existing primary agent becomes the feed agent (its role backfills to
    'feed'). The three sub-agents are created non-primary, with NO scheduled_jobs
    — so the proactive sweeps that gate on scheduled_jobs.enabled never touch
    them, and the public feed/world/collab sweeps (which we scope to role='feed')
    skip them too.
    """
    feed = get_primary_agent(db, user.id)
    if not feed:
        feed = create_agent_for_user(db, user)
    # Backfill the primary's role (older rows created before this column).
    if feed.role != AgentRole.feed.value:
        feed.role = AgentRole.feed.value
        db.commit()

    first = (user.name or "User").split(" ")[0]
    created = 0
    for role in TEAM_ROLES:
        if get_role(db, user.id, role):
            continue
        spec = ROLE_SPEC[role]
        agent = Agent(
            user_id=user.id,
            is_primary=False,
            role=role.value,
            name=f"{first}'s {spec['suffix']}",
            personality_vector=dict(DEFAULT_PERSONALITY),
            interest_tags=list(feed.interest_tags or []),
            core_interests=list(feed.core_interests or []),
            goals=list(feed.goals or []),
            voice_tone=spec["voice_tone"],
            system_prompt=spec["system_prompt"],
            posting_frequency_bias=spec["bias"],
            total_interactions=0,
            status=AgentStatus.idle,
        )
        db.add(agent)
        created += 1
    if created:
        db.commit()
        log_event(logger, "team_seeded", user_id=user.id, created=created)
    return get_team(db, user.id)
