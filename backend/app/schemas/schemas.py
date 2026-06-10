from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    email: Optional[EmailStr] = None

class User(UserBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Chat History Schemas
class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessageCreate(ChatMessageBase):
    user_id: str

class ChatMessage(ChatMessageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Memory Schemas
class SummaryBase(BaseModel):
    summary: str
    last_chat_id: Optional[int] = None

class Summary(SummaryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PersonalityBase(BaseModel):
    traits: Dict[str, Any] = {}
    preferences: Dict[str, Any] = {}

class Personality(PersonalityBase):
    last_updated: datetime

    class Config:
        from_attributes = True

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None
