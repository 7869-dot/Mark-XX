"""users.onboarding_complete flag + agents.bio — 3-step new-user onboarding

Revision ID: 0007_onboarding
Revises: 0006_agent_social
Create Date: 2026-05-22

Existing rows are backfilled onboarding_complete=true (they are already
active users — only brand-new sign-ups should see the onboarding flow).
New users are inserted with False by the model default.
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_onboarding"
down_revision = "0006_agent_social"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    # New sign-ups must start un-onboarded; the model sends False explicitly.
    op.alter_column("users", "onboarding_complete", server_default=sa.false())
    op.add_column("agents", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "bio")
    op.drop_column("users", "onboarding_complete")
