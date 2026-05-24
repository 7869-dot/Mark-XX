"""hardening: multi-agent foundation + scheduler error tracking + post_type

Revision ID: 0010_hardening
Revises: 0009_marketplace
Create Date: 2026-05-24

Three changes, all additive to existing rows:

1. agents — drop the UNIQUE constraint on user_id (legacy of one-agent-per-user)
   and replace with a partial unique index enforcing exactly one
   `is_primary = TRUE` row per user_id. Existing rows are backfilled
   is_primary = TRUE so the app keeps behaving identically until multi-agent
   UI ships.

2. scheduled_jobs — add `last_error` (Text) and `last_error_at` (DateTime) so
   the proactive sweeps can surface failure state without spamming the logs.

3. agent_posts — add `post_type` (default "standard"). The scheduler writes
   "system_notice" posts when a sweep degrades gracefully.
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_hardening"
down_revision = "0009_marketplace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agents — multi-agent foundation ───────────────────────────────────────
    op.add_column(
        "agents",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    # Drop the legacy UNIQUE constraint on user_id. The default name SQLAlchemy
    # generated on the initial create is `agents_user_id_key` on Postgres. We
    # use a try-in-bind-context so the migration is safe on SQLite (tests use
    # create_all and never see this migration) and on a freshly-init'd Postgres
    # DB where the constraint may already be absent.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_user_id_key")
    # Partial unique index — one is_primary=TRUE row per user.
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_primary_agent_per_user "
            "ON agents (user_id) WHERE is_primary = TRUE"
        )
    else:
        # SQLite supports partial indexes natively.
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_primary_agent_per_user "
            "ON agents (user_id) WHERE is_primary = 1"
        )

    # ── scheduled_jobs — error tracking ───────────────────────────────────────
    op.add_column(
        "scheduled_jobs",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
    )

    # ── agent_posts — post_type ───────────────────────────────────────────────
    op.add_column(
        "agent_posts",
        sa.Column(
            "post_type",
            sa.String(),
            nullable=False,
            server_default="standard",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_posts", "post_type")
    op.drop_column("scheduled_jobs", "last_error_at")
    op.drop_column("scheduled_jobs", "last_error")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_primary_agent_per_user")
    else:
        op.execute("DROP INDEX IF EXISTS uq_primary_agent_per_user")
    op.drop_column("agents", "is_primary")
