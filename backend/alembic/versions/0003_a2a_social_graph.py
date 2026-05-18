"""a2a social graph: agent profile cols, interaction cols, connections, discovery log

Revision ID: 0003_a2a_social_graph
Revises: 0002_hardening
Create Date: 2026-05-18

Additive only. Enum columns were created as VARCHAR in 0001, so new enum
values (goal_alignment, pending) need no DB change. Data backfill of
interest_tags / goals and the social_graph -> agent_connections cut-over
is done idempotently in Python at startup (see app.services.profile_sync).
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_a2a_social_graph"
down_revision = "0002_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 2A — agents profile columns
    op.add_column("agents", sa.Column("interest_tags", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("goals", sa.JSON(), nullable=True))
    op.add_column(
        "agents",
        sa.Column("total_interactions", sa.Integer(), nullable=True, server_default="0"),
    )
    op.create_index(
        "ix_agents_reputation_score", "agents", [sa.text("reputation_score DESC")]
    )

    # 2C — agent_interactions new columns
    op.add_column("agent_interactions", sa.Column("initiator_message", sa.Text(), nullable=True))
    op.add_column("agent_interactions", sa.Column("target_response", sa.Text(), nullable=True))
    op.add_column("agent_interactions", sa.Column("shared_goals", sa.JSON(), nullable=True))
    op.add_column(
        "agent_interactions",
        sa.Column("human_a_notified", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.add_column(
        "agent_interactions",
        sa.Column("human_b_notified", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index("ix_agent_interactions_status", "agent_interactions", ["status"])

    # 2B — agent_connections
    op.create_table(
        "agent_connections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_a_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("agent_b_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("compatibility_score", sa.Float(), nullable=True),
        sa.Column("connection_type", sa.String(), nullable=True),
        sa.Column("initiated_by", sa.String(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("human_followed_up", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("interaction_count", sa.Float(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("agent_a_id", "agent_b_id", name="uq_agent_pair"),
    )
    op.create_index("ix_agent_connections_agent_a_id", "agent_connections", ["agent_a_id"])
    op.create_index("ix_agent_connections_agent_b_id", "agent_connections", ["agent_b_id"])

    # 2D — agent_discovery_log
    op.create_table(
        "agent_discovery_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("discovered_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("compatibility_score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("was_acted_on", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("discovered_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_discovery_log_agent_id", "agent_discovery_log", ["agent_id"])
    op.create_index(
        "ix_agent_discovery_log_discovered_agent_id",
        "agent_discovery_log",
        ["discovered_agent_id"],
    )
    op.create_index(
        "ix_agent_discovery_log_discovered_at", "agent_discovery_log", ["discovered_at"]
    )


def downgrade() -> None:
    op.drop_table("agent_discovery_log")
    op.drop_index("ix_agent_connections_agent_b_id", "agent_connections")
    op.drop_index("ix_agent_connections_agent_a_id", "agent_connections")
    op.drop_table("agent_connections")
    op.drop_index("ix_agent_interactions_status", "agent_interactions")
    op.drop_column("agent_interactions", "human_b_notified")
    op.drop_column("agent_interactions", "human_a_notified")
    op.drop_column("agent_interactions", "shared_goals")
    op.drop_column("agent_interactions", "target_response")
    op.drop_column("agent_interactions", "initiator_message")
    op.drop_index("ix_agents_reputation_score", "agents")
    op.drop_column("agents", "total_interactions")
    op.drop_column("agents", "goals")
    op.drop_column("agents", "interest_tags")
