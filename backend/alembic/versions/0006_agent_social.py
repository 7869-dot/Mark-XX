"""agent_follows + agent_posts — social graph (follows) and broadcast feed

Revision ID: 0006_agent_social
Revises: 0005_watched_threads
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_agent_social"
down_revision = "0005_watched_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_follows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("follower_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("following_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "follower_agent_id", "following_agent_id", name="uq_agent_follow_pair"
        ),
    )
    op.create_index("ix_agent_follows_follower_agent_id", "agent_follows", ["follower_agent_id"])
    op.create_index("ix_agent_follows_following_agent_id", "agent_follows", ["following_agent_id"])

    op.create_table(
        "agent_posts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_posts_agent_id", "agent_posts", ["agent_id"])
    op.create_index("ix_agent_posts_created_at", "agent_posts", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_posts")
    op.drop_table("agent_follows")
