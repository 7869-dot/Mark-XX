"""Shared FastAPI dependencies — auth, DB.

current_user_id  — raises 401 if not authenticated
optional_user_id — returns None if not authenticated (used by /chat)
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from auth import verify_jwt
from config import DEV_MODE


async def current_user_id(
    authorization: str | None = Header(None),
    x_user_id:    str | None = Header(None),
) -> str:
    if authorization and authorization.startswith("Bearer "):
        try:
            return verify_jwt(authorization[7:])
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid or expired JWT")
    if DEV_MODE and x_user_id:
        return x_user_id
    raise HTTPException(
        status_code=401,
        detail=(
            "Authentication required. Send 'Authorization: Bearer <jwt>'."
            + (" X-User-Id accepted in DEV_MODE." if DEV_MODE else "")
        ),
    )


async def optional_user_id(
    authorization: str | None = Header(None),
    x_user_id:    str | None = Header(None),
) -> str | None:
    """Returns user_id or None — never raises 401."""
    if authorization and authorization.startswith("Bearer "):
        try:
            return verify_jwt(authorization[7:])
        except ValueError:
            return None
    if DEV_MODE and x_user_id:
        return x_user_id
    return None
