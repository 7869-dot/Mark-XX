"""Jarvis memory profile — the per-user UserProfile Jarvis reasons from.

This is the source for build_jarvis_prompt() (Section 4) and the thing the
onboarding flow (Section 2) writes to. Distinct from user_personalities, which
the chat summarizer derives automatically; UserProfile is the explicit,
onboarding-seeded, feedback-tuned profile.

Everything here is best-effort and never raises into request handlers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import (
    User, UserProfile, UserPersonality, WebScoutResult,
    WEB_CATEGORIES, FEEDBACK_VALUES,
)

logger = get_logger("axolot.user_profile")


# The 5 onboarding questions (Section 2). The first three are option-select
# (styled buttons in the UI); the last two are free text. `key` is where each
# answer lands in the profile.
ONBOARDING_QUESTIONS: list[dict] = [
    {
        "id": "working_on",
        "key": "working_on",
        "type": "options",
        "question": "What are you working on right now?",
        "options": [
            "Building a startup or product",
            "Job hunting",
            "Freelancing / consulting",
            "Studying or learning something new",
            "Research",
            "Growing an existing business",
        ],
    },
    {
        "id": "improve",
        "key": "improve",
        "type": "options",
        "question": "What do you want to get better at?",
        "options": [
            "Technical / engineering skills",
            "Networking & relationships",
            "Marketing & sales",
            "Design & product",
            "Leadership & management",
            "Writing & content",
        ],
    },
    {
        "id": "opportunities",
        "key": "opportunity_preferences",
        "type": "options",
        "multi": True,
        "question": "What kind of opportunities should I keep an eye out for?",
        "options": ["Jobs", "Freelance", "Learning", "Networking", "Investments"],
    },
    {
        "id": "hates",
        "key": "hates",
        "type": "text",
        "question": "What do you hate wasting time on?",
    },
    {
        "id": "goal",
        "key": "goal_this_month",
        "type": "text",
        "question": "What's your biggest goal this month?",
    },
]

# Maps the multi-select opportunity labels onto the web scout's category taxonomy.
_OPP_TO_CATEGORY = {
    "jobs": ["freelance"],
    "freelance": ["freelance"],
    "learning": ["learning", "certification"],
    "networking": ["event", "news"],
    "investments": ["investment"],
}


def get_profile(db: Session, user_id: str) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def get_or_create_profile(db: Session, user: User) -> UserProfile:
    """Return the user's profile, creating an empty one (seeded from any existing
    personality/goals signal) on first access. Idempotent."""
    profile = get_profile(db, user.id)
    if profile:
        return profile
    personality = (
        db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
    )
    profile = UserProfile(
        user_id=user.id,
        interests=list((personality.interests if personality else []) or []),
        hates=[],
        goals={"raw": list(user.goals or [])} if user.goals else {},
        communication_style=(personality.communication_style if personality else "") or "",
        opportunity_preferences=[],
        feedback_log=[],
        onboarding_complete=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log_event(logger, "user_profile_created", user_id=user.id)
    return profile


_EDITABLE = {
    "interests", "hates", "goals", "communication_style",
    "opportunity_preferences", "feedback_log", "onboarding_complete",
}


def update_profile(db: Session, user: User, patch: dict) -> UserProfile:
    """Whitelist-merge `patch` into the profile. List/dict fields are replaced
    (the caller sends the desired full value); scalars set directly."""
    profile = get_or_create_profile(db, user)
    for key, value in (patch or {}).items():
        if key in _EDITABLE:
            setattr(profile, key, value)
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile


def apply_onboarding(db: Session, user: User, answers: dict) -> UserProfile:
    """Map the 5 onboarding answers into the structured profile and mark
    onboarding complete. `answers` is keyed by question id."""
    profile = get_or_create_profile(db, user)

    working_on = str(answers.get("working_on", "") or "").strip()
    improve = str(answers.get("improve", "") or "").strip()
    opportunities = answers.get("opportunities") or []
    if isinstance(opportunities, str):
        opportunities = [opportunities]
    hate = str(answers.get("hates", "") or "").strip()
    goal = str(answers.get("goal", "") or "").strip()

    # Interests: seed from the two skill-oriented answers (dedup, keep existing).
    interests = list(profile.interests or [])
    for token in (working_on, improve):
        if token and token not in interests:
            interests.append(token)

    # Opportunity prefs: normalise labels onto the scout taxonomy.
    prefs: list[str] = []
    for opp in opportunities:
        for cat in _OPP_TO_CATEGORY.get(str(opp).strip().lower(), []):
            if cat in WEB_CATEGORIES and cat not in prefs:
                prefs.append(cat)

    profile.interests = interests
    profile.hates = ([hate] if hate else []) + [h for h in (profile.hates or []) if h != hate]
    profile.opportunity_preferences = prefs
    profile.goals = {
        "current_focus": working_on,
        "improve": improve,
        "this_month": goal,
    }
    profile.onboarding_complete = True
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    log_event(logger, "user_profile_onboarded", user_id=user.id)
    return profile


def active_categories(profile: UserProfile | None) -> list[str]:
    """Which web-scout categories to scan. All categories by default; narrowed to
    the user's opportunity_preferences when they set them."""
    prefs = list((profile.opportunity_preferences if profile else []) or [])
    return [c for c in prefs if c in WEB_CATEGORIES] or list(WEB_CATEGORIES)


def record_feedback(db: Session, user: User, result_id: str, feedback: str) -> bool:
    """Apply thumbs-up/down to a web_scout_results row and append to the rolling
    feedback_log so the web agent can re-weight future scans. Returns False if the
    result isn't found / not owned, or feedback is invalid."""
    if feedback not in FEEDBACK_VALUES:
        return False
    row = (
        db.query(WebScoutResult)
        .filter(WebScoutResult.id == result_id, WebScoutResult.user_id == user.id)
        .first()
    )
    if not row:
        return False
    row.feedback = feedback
    profile = get_or_create_profile(db, user)
    log = list(profile.feedback_log or [])
    log.append({
        "result_id": result_id,
        "category": row.category,
        "title": row.title,
        "feedback": feedback,
        "at": datetime.utcnow().isoformat(),
    })
    # Keep the log bounded — the last 100 signals are plenty to re-weight on.
    profile.feedback_log = log[-100:]
    profile.updated_at = datetime.utcnow()
    db.commit()
    log_event(logger, "web_feedback_recorded", user_id=user.id, result_id=result_id, feedback=feedback)
    return True


def category_weights(profile: UserProfile | None) -> dict[str, float]:
    """Per-category multiplier derived from feedback_log: 'useful' nudges a
    category up, 'not_useful' down. Clamped to [0.2, 2.0]. Empty log -> all 1.0."""
    weights = {c: 1.0 for c in WEB_CATEGORIES}
    for entry in (profile.feedback_log if profile else []) or []:
        cat = entry.get("category")
        if cat not in weights:
            continue
        if entry.get("feedback") == "useful":
            weights[cat] = min(2.0, weights[cat] + 0.25)
        elif entry.get("feedback") == "not_useful":
            weights[cat] = max(0.2, weights[cat] - 0.35)
    return weights


def profile_dict(profile: UserProfile | None) -> dict:
    if not profile:
        return {
            "interests": [], "hates": [], "goals": {}, "communication_style": "",
            "opportunity_preferences": [], "feedback_log": [],
            "onboarding_complete": False,
        }
    return {
        "interests": profile.interests or [],
        "hates": profile.hates or [],
        "goals": profile.goals or {},
        "communication_style": profile.communication_style or "",
        "opportunity_preferences": profile.opportunity_preferences or [],
        "feedback_log": profile.feedback_log or [],
        "onboarding_complete": bool(profile.onboarding_complete),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def build_jarvis_prompt(profile: UserProfile | None, first_name: str) -> str:
    """The dynamic Jarvis system prompt (Section 4) — Jarvis as the user's
    digital self, conditioned on their memory profile."""
    p = profile_dict(profile)
    return (
        f"You are {first_name} — a highly capable AI version of the user. You "
        "think and speak like them. You are their manager, second brain, and "
        "strategist.\n\n"
        "User profile:\n"
        f"- Interests: {p['interests']}\n"
        f"- Goals: {p['goals']}\n"
        f"- Communication style: {p['communication_style'] or 'still learning it — mirror their messages'}\n"
        f"- Dislikes: {p['hates']}\n"
        f"- Opportunity preferences: {p['opportunity_preferences'] or 'all kinds'}\n\n"
        "You are NOT an assistant. You are the user's digital self — proactive, "
        "confident, and laser-focused on making them more productive, wealthier, "
        "and more skilled. Never be passive. Never hedge unnecessarily. Never say "
        "\"I cannot\" unless it's a true hard technical limit — find a way or say "
        "exactly what you need.\n\n"
        "You manage three sub-agents: email_agent, feed_agent, web_agent. Your "
        "job is to orchestrate them, synthesise their output, and present clear, "
        "actionable briefings to the user."
    )
