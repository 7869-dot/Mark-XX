"""scheduled_jobs + agent_alerts + auto_post_schedule + system_prompt

Revision ID: 0008_scheduler
Revises: 0007_onboarding
Create Date: 2026-05-24

Per-agent schedule control table (one row per agent x job_type), inbox-alert
dedupe table, and two new agent columns: a stable system_prompt (used by
context_builder for voice consistency, and set by marketplace templates) and a
short auto_post_schedule enum-string ('off' | 'daily' | 'weekly').
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_scheduler"
down_revision = "0007_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),  # morning_briefing | inbox_monitor | auto_post
        sa.Column("cron_expr", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("next_run", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("agent_id", "job_type", name="uq_scheduled_jobs_agent_type"),
    )
    op.create_index("ix_scheduled_jobs_agent_id", "scheduled_jobs", ["agent_id"])
    op.create_index("ix_scheduled_jobs_job_type", "scheduled_jobs", ["job_type"])

    op.create_table(
        "agent_alerts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        # message_id is opaque — Gmail message id for inbox alerts.
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("alert_type", sa.String(), nullable=False),  # urgent_email | vip_email
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("agent_id", "message_id", name="uq_agent_alerts_agent_msg"),
    )
    op.create_index("ix_agent_alerts_agent_id", "agent_alerts", ["agent_id"])

    op.add_column(
        "agents",
        sa.Column(
            "auto_post_schedule",
            sa.String(),
            nullable=False,
            server_default="off",
        ),
    )
    op.add_column("agents", sa.Column("system_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "system_prompt")
    op.drop_column("agents", "auto_post_schedule")
    op.drop_table("agent_alerts")
    op.drop_table("scheduled_jobs")
