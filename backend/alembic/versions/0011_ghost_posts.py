"""ghost_posts — generation records for autonomous owner-voice posting

Revision ID: 0011_ghost_posts
Revises: 0010_hardening
Create Date: 2026-05-28

A GhostPost is the record of an agent posting *for its owner* (spec §7). It
captures the rotation category (post_type), the generated content, the approval
lifecycle (auto_posted | pending_review | rejected), and — once live — a link to
the public agent_posts row it spawned.

Runtime DDL is still driven by Base.metadata.create_all + core.schema_sync; this
migration keeps the Alembic history complete and reproducible for fresh setups.
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_ghost_posts"
down_revision = "0010_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ghost_posts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "approval_status",
            sa.String(),
            nullable=False,
            server_default="auto_posted",
        ),
        sa.Column(
            "agent_post_id", sa.String(), sa.ForeignKey("agent_posts.id"), nullable=True
        ),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ghost_posts_owner_id", "ghost_posts", ["owner_id"])
    op.create_index("ix_ghost_posts_agent_id", "ghost_posts", ["agent_id"])
    op.create_index("ix_ghost_posts_post_type", "ghost_posts", ["post_type"])
    op.create_index(
        "ix_ghost_posts_approval_status", "ghost_posts", ["approval_status"]
    )
    op.create_index("ix_ghost_posts_generated_at", "ghost_posts", ["generated_at"])


def downgrade() -> None:
    op.drop_table("ghost_posts")
