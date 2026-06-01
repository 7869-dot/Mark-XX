"""agent_task_results + agents.role — Jarvis orchestration (Sprint 2 / four-agent)

Revision ID: 0012_agent_task_results
Revises: 0011_ghost_posts
Create Date: 2026-06-02

agent_task_results stores the email agent's drafts (requires_approval=True,
never sent in V1). agents.role backs the four-agent architecture; existing rows
default to 'posting' so the historical primary agent is unchanged.

Runtime DDL is driven by Base.metadata.create_all + core.schema_sync; this
migration keeps the Alembic history complete for fresh prod setups.
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_agent_task_results"
down_revision = "0011_ghost_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # agents.role (idempotent — the column may already exist via schema_sync).
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("agents")}
    if "role" not in cols:
        op.add_column(
            "agents",
            sa.Column("role", sa.String(length=16), nullable=False, server_default="posting"),
        )
        op.create_index("ix_agents_role", "agents", ["role"])

    if "agent_task_results" not in insp.get_table_names():
        op.create_table(
            "agent_task_results",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("agent_role", sa.String(length=20), nullable=False, server_default="email"),
            sa.Column("draft_content", sa.Text(), nullable=False, server_default=""),
            sa.Column("subject_line", sa.String(length=500), server_default=""),
            sa.Column("recipient_hint", sa.String(length=200), server_default=""),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("approved", sa.Boolean(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_agent_task_results_user_id", "agent_task_results", ["user_id"])
        op.create_index("ix_agent_task_results_created_at", "agent_task_results", ["created_at"])
        op.create_index(
            "ix_agent_task_results_user_approved", "agent_task_results", ["user_id", "approved"]
        )


def downgrade() -> None:
    op.drop_table("agent_task_results")
    # Leave agents.role in place — dropping it would break the four-agent code.
