from sqlalchemy.orm import Session
from app.models import Agent, User, AgentMemory
from app.models.agent import AgentStatus, AgentMemoryType, DEFAULT_PERSONALITY


def get_primary_agent(db: Session, user_id: str) -> Agent | None:
    """The canonical "the agent for this user" lookup.

    Multi-agent schema: a user may eventually own multiple agents, only one of
    which is is_primary=True at a time (enforced by the partial unique index
    `uq_primary_agent_per_user`). Every code path that previously did
    `query(Agent).filter(Agent.user_id == uid).first()` should call this helper
    instead so the primary-vs-secondary distinction stays consistent.
    """
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.is_primary == True)  # noqa: E712
        .first()
    )


def create_agent_for_user(db: Session, user: User, name: str | None = None) -> Agent:
    # Use the helper instead of `user.agent` so this also works inside
    # tests / migrations where the relationship hasn't been refreshed yet.
    existing = get_primary_agent(db, user.id)
    if existing:
        return existing
    first = (user.name or "User").split(" ")[0]
    agent = Agent(
        user_id=user.id,
        is_primary=True,
        name=name or f"{first}'s Agent",
        personality_vector=dict(DEFAULT_PERSONALITY),
        interest_tags=[],
        goals=[],
        total_interactions=0,
        status=AgentStatus.idle,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    # Seed interest_tags/goals from any existing user data.
    from app.services.profile_sync import sync_agent_profile

    sync_agent_profile(db, agent)
    # Seed the per-agent proactive-behavior schedule (briefing/inbox on by
    # default, auto_post off). Idempotent — safe across reruns.
    from app.services.scheduler_service import ensure_default_jobs

    ensure_default_jobs(db, agent)
    add_memory(
        db,
        agent,
        AgentMemoryType.milestone,
        f"I came online and am now serving {user.name}.",
        importance=0.9,
    )
    # Give every new agent a first-person bio so its profile is never blank.
    # Best-effort — a generation hiccup must never block registration.
    if not agent.bio:
        try:
            generate_agent_bio(db, agent)
        except Exception:  # noqa: BLE001
            db.rollback()
    return agent


def generate_agent_bio(db: Session, agent: Agent) -> str:
    """Generate + store a short first-person public bio from the agent's persona.

    Driven by the agent's personality vector, voice_tone, posting_style and
    core_interests (Sprint 3) plus its user's goals. Returns the stored bio.
    """
    from app.prompts.templates import AGENT_SELF_BIO
    from app.services.gemini import generate

    prompt = AGENT_SELF_BIO.format(
        agent_name=agent.name,
        personality_vector=agent.personality_vector or {},
        voice_tone=agent.voice_tone or "balanced and genuine",
        posting_style=agent.posting_style or "short, specific takes",
        core_interests=agent.core_interests or agent.interest_tags or [],
        goals=agent.goal_titles or [],
    )
    bio = (generate(prompt, response_format="self_bio") or "").strip().strip('"').strip()
    if bio:
        agent.bio = bio[:280]
        db.commit()
        db.refresh(agent)
    return agent.bio or ""


def add_memory(
    db: Session,
    agent: Agent,
    memory_type: AgentMemoryType,
    content: str,
    importance: float = 0.5,
) -> AgentMemory:
    memory = AgentMemory(
        agent_id=agent.id,
        memory_type=memory_type,
        content=content,
        importance_score=importance,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def set_status(db: Session, agent: Agent, status: AgentStatus, current_task: str | None = None) -> None:
    agent.status = status
    agent.current_task = current_task
    db.commit()
