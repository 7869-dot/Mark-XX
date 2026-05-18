"""google integration token storage on users

Revision ID: 0004_google_tokens
Revises: 0003_a2a_social_graph
Create Date: 2026-05-18

Additive only. Tokens are stored Fernet-encrypted (see app.services.google_auth).
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_google_tokens"
down_revision = "0003_a2a_social_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_access_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_token_expiry", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("google_scopes", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("gmail_connected", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("calendar_connected", sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "calendar_connected")
    op.drop_column("users", "gmail_connected")
    op.drop_column("users", "google_scopes")
    op.drop_column("users", "google_token_expiry")
    op.drop_column("users", "google_refresh_token")
    op.drop_column("users", "google_access_token")
