"""Single-use invite codes — the growth loop.

A user generates a short code, shares axolot.app/join?code=XXXXXXXX, and when a
new user redeems it on signup the inviter's agent sends a warm welcome DM.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Index

from app.core.db import Base


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 8-char human-shareable code (see services.invites.generate_code).
    code = Column(String, unique=True, nullable=False, index=True)
    created_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL until redeemed — single-use is enforced by checking this is NULL.
    used_by_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_invite_codes_creator", "created_by_user_id"),)
