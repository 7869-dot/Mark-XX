"""hardening: refresh tokens, scheduler locks, reputation events, new columns

Revision ID: 0002_hardening
Revises: 0001_initial
Create Date: 2026-05-15

Additive only. Does not drop or alter existing data.

NOTE: `alembic revision --autogenerate` requires a live DB to diff against the
model metadata, which is not available in this build environment. This file was
written by hand to exactly mirror the new SQLAlchemy models in
app/models/system.py plus the two added columns, and reviewed against them.
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_hardening"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("jti", sa.String(), nullable=False, unique=True),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"])

    op.create_table(
        "scheduler_locks",
        sa.Column("job_id", sa.String(), primary_key=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "reputation_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_reputation_events_agent_id", "reputation_events", ["agent_id"])

    op.add_column(
        "tasks",
        sa.Column("task_timeout_minutes", sa.Integer(), nullable=True, server_default="10"),
    )
    op.add_column(
        "agent_interactions",
        sa.Column("last_contacted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_agent_interactions_last_contacted_at",
        "agent_interactions",
        ["last_contacted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_interactions_last_contacted_at", "agent_interactions")
    op.drop_column("agent_interactions", "last_contacted_at")
    op.drop_column("tasks", "task_timeout_minutes")
    op.drop_index("ix_reputation_events_agent_id", "reputation_events")
    op.drop_table("reputation_events")
    op.drop_table("scheduler_locks")
    op.drop_index("ix_refresh_tokens_jti", "refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", "refresh_tokens")
    op.drop_table("refresh_tokens")
