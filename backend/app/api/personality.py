"""Speech-profile init endpoint — wired to the onboarding step-2 tone survey.

Accepts 5 categorical answers and the optional signature word, writes them
directly into UserPersonality so day-1 chat already mirrors the user's voice
before any chat history exists.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User
from app.services.speech_profile import apply_onboarding_answers

router = APIRouter(prefix="/agent", tags=["personality"])


class PersonalityInitBody(BaseModel):
    avg_sentence_length: str = Field(..., pattern="^(short|medium|long)$")
    formality: str = Field(..., pattern="^(casual|mixed|formal)$")
    emoji_usage: str = Field(..., pattern="^(none|occasional|frequent)$")
    punctuation_style: str = Field(..., pattern="^(minimal|standard|heavy)$")
    signature_word: str | None = Field(default=None, max_length=64)


@router.post("/personality-init")
def personality_init(
    body: PersonalityInitBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = apply_onboarding_answers(db, user.id, body.model_dump())
    return envelope({
        "avg_sentence_length": row.avg_sentence_length,
        "formality": row.formality,
        "emoji_usage": row.emoji_usage,
        "punctuation_style": row.punctuation_style,
        "signature_word": row.signature_word,
    })


@router.get("/personality")
def personality_get(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models import UserPersonality
    row = (
        db.query(UserPersonality)
        .filter(UserPersonality.user_id == user.id)
        .first()
    )
    if not row:
        return envelope({
            "avg_sentence_length": None,
            "formality": None,
            "emoji_usage": None,
            "punctuation_style": None,
            "signature_word": None,
            "sample_phrases": [],
        })
    return envelope({
        "avg_sentence_length": row.avg_sentence_length,
        "formality": row.formality,
        "emoji_usage": row.emoji_usage,
        "punctuation_style": row.punctuation_style,
        "signature_word": row.signature_word,
        "sample_phrases": row.sample_phrases or [],
    })
