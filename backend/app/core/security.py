import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User
from app.models.system import RefreshToken


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google", auto_error=False)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access", **(extra or {})}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, db: Session) -> str:
    """Issue a refresh token and register its jti so it can be rotated exactly once."""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh", "jti": jti}
    db.add(RefreshToken(user_id=subject, jti=jti, used=False))
    db.commit()
    return jwt.encode(payload, settings.JWT_REFRESH_SECRET, algorithm=settings.JWT_ALGORITHM)


def rotate_refresh_token(token: str, db: Session) -> tuple[str, str]:
    """Validate a refresh token, mark it used atomically, and issue a fresh pair.

    Defeats the refresh race: the first request to flip used=False -> True wins;
    a concurrent replay finds used=True and is rejected.
    """
    payload = decode_token(token, refresh=True)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=401, detail="Malformed refresh token")

    record = db.query(RefreshToken).filter(RefreshToken.jti == jti).with_for_update(nowait=False).first() \
        if not settings.DATABASE_URL.startswith("sqlite") \
        else db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

    if not record:
        raise HTTPException(status_code=401, detail="Unknown refresh token")
    if record.used:
        raise HTTPException(status_code=401, detail="Refresh token already used")

    record.used = True
    record.used_at = datetime.utcnow()
    db.commit()

    return create_access_token(user_id), create_refresh_token(user_id, db)


def decode_token(token: str, refresh: bool = False) -> dict:
    secret = settings.JWT_REFRESH_SECRET if refresh else settings.JWT_SECRET
    try:
        return jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
