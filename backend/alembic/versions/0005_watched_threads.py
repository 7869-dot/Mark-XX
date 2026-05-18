"""watched_threads table for Gmail thread monitoring

Revision ID: 0005_watched_threads
Revises: 0004_google_tokens
Create Date: 2026-05-18

Stores ONLY thread ids + bookkeeping. No email content is ever persisted.
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_watched_threads"
down_revision = "0004_google_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watched_threads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_id", sa.String(), nullable=True),
        sa.Column("check_interval_hours", sa.Integer(), nullable=True, server_default="4"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_watched_threads_agent_id", "watched_threads", ["agent_id"])
    op.create_index("ix_watched_threads_user_id", "watched_threads", ["user_id"])
    op.create_index("ix_watched_threads_thread_id", "watched_threads", ["thread_id"])


def downgrade() -> None:
    op.drop_table("watched_threads")
