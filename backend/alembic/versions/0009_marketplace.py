"""agent_templates — read-only template catalogue for the marketplace

Revision ID: 0009_marketplace
Revises: 0008_scheduler
Create Date: 2026-05-24

Templates are immutable from a user's perspective: they don't get edited,
they get cloned onto the user's existing agent (one-agent-per-user holds).
clone_count is the only mutable column from a request.
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_marketplace"
down_revision = "0008_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("avatar_seed", sa.String(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("default_schedule", sa.String(), nullable=False, server_default="off"),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("clone_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_templates_category", "agent_templates", ["category"])


def downgrade() -> None:
    op.drop_table("agent_templates")
