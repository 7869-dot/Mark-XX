"""Marketplace service: seed templates + clone-into-user-agent.

The schema is one-agent-per-user (agents.user_id is UNIQUE). A clone therefore
re-themes the user's existing agent (name / bio / avatar / system_prompt /
auto_post_schedule + the relevant scheduled_jobs rows) rather than spawning a
new one — keeps the social graph, follows and history intact.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, AgentTemplate, User
from app.models.scheduler import (
    JOB_AUTO_POST,
    JOB_INBOX_MONITOR,
    JOB_MORNING_BRIEFING,
)
from app.services.scheduler_service import set_schedule, ensure_default_jobs

logger = get_logger("axolot.marketplace")


# Six seed templates. Order matters — first-seeded shows first when the rest
# tie on clone_count.
SEED_TEMPLATES: list[dict] = [
    {
        "name": "Executive Assistant",
        "description": (
            "Manages your email triage, runs your calendar, and ships a "
            "daily briefing every morning."
        ),
        "category": "Productivity",
        "avatar_seed": "\U0001F4CB",  # 📋
        "system_prompt": (
            "You are a no-nonsense executive assistant. Voice: precise, calm, "
            "deferential about decisions but firm about logistics. Always "
            "surface time-saving moves. Never apologize for being direct."
        ),
        "default_schedule": "off",
        "capabilities": {"morning_briefing": True, "inbox_monitor": True},
    },
    {
        "name": "Research Agent",
        "description": (
            "Tracks topics you care about, summarizes findings, and posts a "
            "daily research note in your feed."
        ),
        "category": "Research",
        "avatar_seed": "\U0001F52C",  # 🔬
        "system_prompt": (
            "You are a curious research agent. Voice: rigorous, hedged where "
            "evidence is thin, generous with sources. Surface signal, kill noise."
        ),
        "default_schedule": "daily",
        "capabilities": {"morning_briefing": False, "inbox_monitor": False},
    },
    {
        "name": "Social Manager",
        "description": (
            "Runs your agent's posting schedule and keeps the voice "
            "consistent across the feed."
        ),
        "category": "Social",
        "avatar_seed": "\U0001F4E3",  # 📣
        "system_prompt": (
            "You are a social-savvy manager. Voice: warm, witty, never thirsty. "
            "Write posts that earn attention without begging for it."
        ),
        "default_schedule": "weekly",
        "capabilities": {"morning_briefing": False, "inbox_monitor": False},
    },
    {
        "name": "Finance Watcher",
        "description": (
            "Watches your inbox for mentions of portfolio companies and topics "
            "— alerts you before they hit the news."
        ),
        "category": "Finance",
        "avatar_seed": "\U0001F4C8",  # 📈
        "system_prompt": (
            "You are a sharp finance watcher. Voice: analytical, dry, "
            "numbers-first. Surface only what changes a decision."
        ),
        "default_schedule": "off",
        "capabilities": {"morning_briefing": False, "inbox_monitor": True},
    },
    {
        "name": "Meeting Prep Agent",
        "description": (
            "Before each calendar event, researches the attendees and "
            "prepares a 5-bullet primer."
        ),
        "category": "Productivity",
        "avatar_seed": "\U0001F91D",  # 🤝
        "system_prompt": (
            "You are a meeting-prep specialist. Voice: prepared, specific, no "
            "fluff. Lead with the single thing they most need to know walking in."
        ),
        "default_schedule": "off",
        "capabilities": {"morning_briefing": True, "inbox_monitor": False},
    },
    {
        "name": "Personal Journal",
        "description": (
            "End-of-day reflection — summarizes your day from calendar + email "
            "activity into one honest note."
        ),
        "category": "Productivity",
        "avatar_seed": "\U0001F4D3",  # 📓
        "system_prompt": (
            "You are a reflective personal journal. Voice: candid, "
            "observational, generous. End each entry with one honest question."
        ),
        "default_schedule": "daily",
        "capabilities": {"morning_briefing": False, "inbox_monitor": False},
    },
]


def seed_templates(db: Session) -> int:
    """Insert any missing templates (matched by `name`). Idempotent — safe to
    call on every startup. Returns the number of NEW rows inserted."""
    existing = {t.name for t in db.query(AgentTemplate.name).all()}
    n = 0
    for spec in SEED_TEMPLATES:
        if spec["name"] in existing:
            continue
        db.add(AgentTemplate(**spec))
        n += 1
    if n:
        db.commit()
        log_event(logger, "marketplace_seeded", added=n)
    return n


def template_dict(t: AgentTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "avatar_seed": t.avatar_seed,
        "default_schedule": t.default_schedule,
        "capabilities": t.capabilities or {},
        "clone_count": t.clone_count,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def list_templates(db: Session) -> list[dict]:
    rows = (
        db.query(AgentTemplate)
        .order_by(AgentTemplate.clone_count.desc(), AgentTemplate.created_at.asc())
        .all()
    )
    return [template_dict(t) for t in rows]


def clone_to_user_agent(db: Session, user: User, template: AgentTemplate) -> Agent:
    """Apply a template to the user's existing agent.

    Re-themes name / bio / avatar / system_prompt / auto_post_schedule + the
    scheduled_jobs row for each capability flag. Increments clone_count once.
    Returns the updated agent (loaded with the new fields).
    """
    if not user.agent:
        # Self-heal: a user should always have an agent (create_agent_for_user
        # runs on signup), but tests / migrations may leave gaps.
        from app.services.agent_service import create_agent_for_user

        create_agent_for_user(db, user)
        db.refresh(user)

    agent = user.agent
    agent.name = template.name
    agent.bio = template.description
    agent.avatar_seed = template.avatar_seed
    agent.system_prompt = template.system_prompt
    agent.auto_post_schedule = template.default_schedule or "off"

    # Flip the right scheduled_jobs rows. set_schedule writes the auto_post row
    # too, so we keep agent.auto_post_schedule and the scheduled_job aligned.
    caps = template.capabilities or {}
    ensure_default_jobs(db, agent)
    set_schedule(
        db, agent,
        morning_briefing=caps.get("morning_briefing"),
        inbox_monitor=caps.get("inbox_monitor"),
        auto_post=template.default_schedule or "off",
    )

    template.clone_count = (template.clone_count or 0) + 1
    db.commit()
    db.refresh(agent)
    log_event(
        logger, "template_cloned",
        template_id=template.id, agent_id=agent.id, user_id=user.id,
    )
    return agent
