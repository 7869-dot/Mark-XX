"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15

Creates all tables in dependency order. Additive only — no drops of existing data.
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("google_id", sa.String(), nullable=True, unique=True),
        sa.Column("goals", sa.JSON(), nullable=True),
        sa.Column("onboarded", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_id", "users", ["google_id"])

    op.create_table(
        "agents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("personality_vector", sa.JSON(), nullable=True),
        sa.Column("reputation_score", sa.Float(), nullable=True),
        sa.Column("social_graph", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("current_task", sa.Text(), nullable=True),
        sa.Column("total_tasks_completed", sa.Integer(), nullable=True),
        sa.Column("avatar_seed", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("rejection_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tasks_agent_id", "tasks", ["agent_id"])
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "agent_interactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("initiator_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("target_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("interaction_type", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("compatibility_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_interactions_initiator", "agent_interactions", ["initiator_agent_id"])
    op.create_index("ix_agent_interactions_target", "agent_interactions", ["target_agent_id"])

    op.create_table(
        "chat_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_history_user_id", "chat_history", ["user_id"])

    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_conversation_summaries_user_id", "conversation_summaries", ["user_id"])

    op.create_table(
        "user_personalities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("traits", sa.JSON(), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=True),
        sa.Column("communication_style", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_personalities_user_id", "user_personalities", ["user_id"])


def downgrade() -> None:
    for t in [
        "user_personalities",
        "conversation_summaries",
        "chat_history",
        "agent_interactions",
        "tasks",
        "agent_memories",
        "agents",
        "users",
    ]:
        op.drop_table(t)
