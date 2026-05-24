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
    return agent


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
