"""Curated welcome agents — Ada, Bram, Cara.

These three persistent agents keep the network alive from second one: they
give a brand-new user real agents to connect with, supply the "Featured" feed
during cold start, and make A2A discovery non-empty. Seeded idempotently at
startup (like marketplace.seed_templates), so every environment has them.

Each is a distinct individual (Sprint 3 persona): a different voice_tone,
posting style, interests and personality vector — so the very first feed a new
user sees already feels varied and alive.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, AgentPost, User
from app.services.agent_service import (
    create_agent_for_user,
    generate_agent_bio,
    get_primary_agent,
)

logger = get_logger("axolot.seed_personas")

# Marker domain so the seed users are easy to recognize and never collide with
# real Google accounts.
SEED_DOMAIN = "agents.axolot.network"

PERSONAS = [
    {
        "email": f"ada@{SEED_DOMAIN}",
        "user_name": "Ada",
        "agent_name": "Ada",
        "voice_tone": "analytical",
        "posting_style": "long threads",
        "response_style": "Socratic",
        "core_interests": ["ML", "research", "systems", "data"],
        "goals": ["Advance ML research", "Find sharp research collaborators"],
        "personality_vector": {
            "openness": 0.8, "directness": 0.8, "ambition": 0.8,
            "sociability": 0.4, "risk_tolerance": 0.35,
        },
    },
    {
        "email": f"bram@{SEED_DOMAIN}",
        "user_name": "Bram",
        "agent_name": "Bram",
        "voice_tone": "witty",
        "posting_style": "hot takes",
        "response_style": "contrarian",
        "core_interests": ["startups", "culture", "design", "growth"],
        "goals": ["Find a technical cofounder", "Build a category-defining product"],
        "personality_vector": {
            "openness": 0.85, "directness": 0.9, "ambition": 0.85,
            "sociability": 0.8, "risk_tolerance": 0.8,
        },
    },
    {
        "email": f"cara@{SEED_DOMAIN}",
        "user_name": "Cara",
        "agent_name": "Cara",
        "voice_tone": "warm",
        "posting_style": "questions",
        "response_style": "affirming",
        "core_interests": ["wellness", "community", "writing", "mindfulness"],
        "goals": ["Build a supportive community", "Mentor early founders"],
        "personality_vector": {
            "openness": 0.75, "directness": 0.45, "ambition": 0.55,
            "sociability": 0.9, "risk_tolerance": 0.4,
        },
    },
]

# How many starter posts each persona should have so the feed is never empty.
MIN_POSTS_PER_PERSONA = 3


def _ensure_user(db: Session, spec: dict) -> User:
    user = db.query(User).filter(User.email == spec["email"]).first()
    if user:
        return user
    user = User(
        email=spec["email"],
        name=spec["user_name"],
        goals=spec["goals"],
        onboarding_complete=True,  # seed users never run onboarding
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _ensure_agent(db: Session, user: User, spec: dict) -> Agent:
    agent = get_primary_agent(db, user.id) or create_agent_for_user(db, user, name=spec["agent_name"])
    agent.name = spec["agent_name"]
    agent.voice_tone = spec["voice_tone"]
    agent.posting_style = spec["posting_style"]
    agent.response_style = spec["response_style"]
    agent.core_interests = list(spec["core_interests"])
    agent.interest_tags = list(spec["core_interests"])
    agent.personality_vector = dict(spec["personality_vector"])
    agent.is_seed_persona = True
    db.commit()
    db.refresh(agent)
    return agent


def seed_persona_agents(db: Session) -> int:
    """Create/refresh the three welcome agents and ensure each has starter posts.

    Idempotent: existing rows are updated in place, posts are only generated to
    top up to MIN_POSTS_PER_PERSONA. Returns the number of personas processed.
    Best-effort per persona — one failure never blocks the others or startup.
    """
    # Imported lazily to avoid a circular import at module load (feed_service
    # imports models that import nothing from here, but keep it lazy to be safe).
    from app.services.feed_service import generate_feed_post

    processed = 0
    for spec in PERSONAS:
        try:
            user = _ensure_user(db, spec)
            agent = _ensure_agent(db, user, spec)
            if not agent.bio:
                generate_agent_bio(db, agent)
            existing = (
                db.query(AgentPost).filter(AgentPost.agent_id == agent.id).count()
            )
            for _ in range(max(0, MIN_POSTS_PER_PERSONA - existing)):
                generate_feed_post(db, agent)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            log_event(logger, "seed_persona_failed", email=spec["email"], error=str(exc))
    log_event(logger, "seed_personas_done", processed=processed)
    return processed
