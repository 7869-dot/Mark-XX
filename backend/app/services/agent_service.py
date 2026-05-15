from sqlalchemy.orm import Session
from app.models import Agent, User, AgentMemory
from app.models.agent import AgentStatus, AgentMemoryType, DEFAULT_PERSONALITY


def create_agent_for_user(db: Session, user: User, name: str | None = None) -> Agent:
    if user.agent:
        return user.agent
    first = (user.name or "User").split(" ")[0]
    agent = Agent(
        user_id=user.id,
        name=name or f"{first}'s Agent",
        personality_vector=dict(DEFAULT_PERSONALITY),
        status=AgentStatus.idle,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
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
