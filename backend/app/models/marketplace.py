"""AgentTemplate — read-only marketplace catalogue.

A template is the persona + default schedule that gets stamped onto a user's
existing agent via POST /marketplace/{id}/clone. The schema is one agent per
user (see agents.user_id unique constraint) — cloning intentionally re-themes
the user's agent rather than creating a second one.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    # Productivity | Social | Research | Finance — kept as a free-form string
    # so the frontend tab list can grow without a migration.
    category = Column(String, nullable=False, index=True)
    avatar_seed = Column(String, nullable=False)
    # Stamped onto agents.system_prompt on clone — drives voice consistency.
    system_prompt = Column(Text, nullable=False)
    # 'off' | 'daily' | 'weekly' — stamped onto agents.auto_post_schedule on clone.
    default_schedule = Column(String, nullable=False, default="off")
    # Free-form: what to flip in scheduled_jobs on clone. Today: keys
    # 'morning_briefing', 'inbox_monitor' (bool). 'auto_post' lives separately
    # in default_schedule.
    capabilities = Column(JSON, default=dict)
    clone_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
