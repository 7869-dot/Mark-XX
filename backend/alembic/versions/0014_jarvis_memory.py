"""user_profiles + web_scout_results + agent_run_log — Jarvis memory (Section 7)

Revision ID: 0014_jarvis_memory
Revises: 0013_jarvis_command_modes
Create Date: 2026-06-02

The Jarvis manager overhaul's persistent memory: the per-user profile Jarvis
tunes over time, the web scout's surfaced opportunities, and a run log that
powers the agent status panel.

Runtime DDL is driven by Base.metadata.create_all + core.schema_sync; this keeps
the Alembic history complete for fresh prod setups.
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_jarvis_memory"
down_revision = "0013_jarvis_command_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if "user_profiles" not in existing:
        op.create_table(
            "user_profiles",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("interests", sa.JSON(), nullable=True),
            sa.Column("hates", sa.JSON(), nullable=True),
            sa.Column("goals", sa.JSON(), nullable=True),
            sa.Column("communication_style", sa.Text(), server_default=""),
            sa.Column("opportunity_preferences", sa.JSON(), nullable=True),
            sa.Column("feedback_log", sa.JSON(), nullable=True),
            sa.Column("onboarding_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        )
        op.create_index("ix_user_profiles_user", "user_profiles", ["user_id"], unique=True)

    if "web_scout_results" not in existing:
        op.create_table(
            "web_scout_results",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.Text(), nullable=False, server_default=""),
            sa.Column("url", sa.Text(), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("category", sa.String(length=32), nullable=False, server_default="news"),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("feedback", sa.String(length=16), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_web_scout_results_user_id", "web_scout_results", ["user_id"])
        op.create_index("ix_web_scout_user_created", "web_scout_results", ["user_id", "created_at"])
        op.create_index("ix_web_scout_user_category", "web_scout_results", ["user_id", "category"])

    if "agent_run_log" not in existing:
        op.create_table(
            "agent_run_log",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_name", sa.String(length=32), nullable=False),
            sa.Column("ran_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("report_summary", sa.Text(), server_default=""),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="ok"),
        )
        op.create_index("ix_agent_run_log_user_id", "agent_run_log", ["user_id"])
        op.create_index("ix_agent_run_log_user_agent_ran", "agent_run_log", ["user_id", "agent_name", "ran_at"])


def downgrade() -> None:
    op.drop_table("agent_run_log")
    op.drop_table("web_scout_results")
    op.drop_table("user_profiles")
