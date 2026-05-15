"""Seed a few demo agents so the network graph and discovery have something to show.

Usage:
    python seed.py
"""
import random
from datetime import datetime, timedelta

from app.core.db import Base, engine, SessionLocal
from app.models import User, UserPersonality, AgentMemory
from app.models.agent import AgentMemoryType
from app.services.agent_service import create_agent_for_user


DEMO_USERS = [
    ("layla@axolot.dev", "Layla Hassan", ["fundraising", "fintech", "early-stage"],
     {"openness": 0.75, "directness": 0.8, "ambition": 0.9, "sociability": 0.7, "risk_tolerance": 0.8}),
    ("kenji@axolot.dev", "Kenji Tanaka", ["ml-research", "papers", "open-source"],
     {"openness": 0.85, "directness": 0.6, "ambition": 0.7, "sociability": 0.4, "risk_tolerance": 0.5}),
    ("ana@axolot.dev", "Ana Rojas", ["growth", "B2B SaaS", "outbound"],
     {"openness": 0.6, "directness": 0.85, "ambition": 0.85, "sociability": 0.8, "risk_tolerance": 0.7}),
    ("jordan@axolot.dev", "Jordan Pierce", ["design-systems", "founders", "creative"],
     {"openness": 0.9, "directness": 0.55, "ambition": 0.7, "sociability": 0.6, "risk_tolerance": 0.6}),
    ("priya@axolot.dev", "Priya Menon", ["data-eng", "platform", "hiring"],
     {"openness": 0.65, "directness": 0.75, "ambition": 0.8, "sociability": 0.55, "risk_tolerance": 0.45}),
    ("dmitri@axolot.dev", "Dmitri Volkov", ["security", "infra", "consulting"],
     {"openness": 0.55, "directness": 0.9, "ambition": 0.7, "sociability": 0.3, "risk_tolerance": 0.4}),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for email, name, interests, pv in DEMO_USERS:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                continue
            user = User(email=email, name=name, goals=[
                f"Find collaborators in {interests[0]}",
                "Ship a meaningful project this quarter",
            ], onboarded={"completed": True, "step": 4})
            db.add(user)
            db.commit()
            db.refresh(user)

            agent = create_agent_for_user(db, user)
            agent.personality_vector = pv
            agent.reputation_score = random.uniform(55, 85)
            agent.total_tasks_completed = random.randint(3, 40)
            agent.created_at = datetime.utcnow() - timedelta(days=random.randint(7, 90))

            personality = UserPersonality(
                user_id=user.id,
                traits={"primary": interests[0]},
                interests=interests,
                communication_style="direct and warm",
                notes=f"Interested in {', '.join(interests)}",
            )
            db.add(personality)

            for _ in range(3):
                m = AgentMemory(
                    agent_id=agent.id,
                    memory_type=AgentMemoryType.task_outcome,
                    content=f"Helped {name.split()[0]} make progress on {random.choice(interests)}.",
                    importance_score=random.uniform(0.4, 0.8),
                )
                db.add(m)
            db.commit()
            print(f"Seeded agent for {name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
