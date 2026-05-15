from pydantic import BaseModel
from typing import Optional


class GoogleAuthRequest(BaseModel):
    # In stub mode this can be a fake email/name. In real mode this would be a Google id_token.
    id_token: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    onboarded: bool


class RefreshRequest(BaseModel):
    refresh_token: str
