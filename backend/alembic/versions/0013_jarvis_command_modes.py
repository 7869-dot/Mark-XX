"""schedule_drafts + post_drafts + chat_history.mode — Jarvis command modes (3A)

Revision ID: 0013_jarvis_command_modes
Revises: 0012_agent_task_results
Create Date: 2026-06-03

One migration, two new draft tables (schedule mode + post mode) plus a `mode`
column on chat_history so Jarvis command-mode turns are tagged and still feed
the existing ConversationSummary pipeline (which reads role/content only).

Runtime DDL is driven by Base.metadata.create_all + core.schema_sync; this keeps
the Alembic history complete for fresh prod setups.
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_jarvis_command_modes"
down_revision = "0012_agent_task_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "mode" not in {c["name"] for c in insp.get_columns("chat_history")}:
        op.add_column("chat_history", sa.Column("mode", sa.String(length=20), nullable=True))

    if "schedule_drafts" not in insp.get_table_names():
        op.create_table(
            "schedule_drafts",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("proposed_datetime", sa.DateTime(), nullable=True),
            sa.Column("duration_minutes", sa.Integer(), nullable=True),
            sa.Column("attendees_hint", sa.JSON(), nullable=True),
            sa.Column("notes", sa.Text(), server_default=""),
            sa.Column("approved", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_schedule_drafts_user_id", "schedule_drafts", ["user_id"])
        op.create_index("ix_schedule_drafts_user_approved", "schedule_drafts", ["user_id", "approved"])

    if "post_drafts" not in insp.get_table_names():
        op.create_table(
            "post_drafts",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("island_hint", sa.String(length=200), server_default=""),
            sa.Column("approved", sa.Boolean(), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_post_drafts_user_id", "post_drafts", ["user_id"])
        op.create_index("ix_post_drafts_user_approved", "post_drafts", ["user_id", "approved"])


def downgrade() -> None:
    op.drop_table("post_drafts")
    op.drop_table("schedule_drafts")
    op.drop_column("chat_history", "mode")
