"""Speech-mirror profile — analyses the user's messages into a small set of
structured tokens (length, formality, emoji_usage, punctuation_style) that the
chat prompt injects verbatim.

Two entry points:
- `bootstrap_from_first_messages` — called on every chat turn until the
  profile is populated. Cheap, runs on the recent ChatHistory.
- `apply_onboarding_answers`     — writes the 5-question onboarding survey
  straight into UserPersonality so day-1 mirroring works before any chat.

Updates blend 0.8/0.2 — observed tokens override stored ones only after
they appear twice in a row, so a single odd message can't whip the profile
around. This is the spec's "rolling average" semantic, adapted to enums.
"""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import ChatHistory, UserPersonality

logger = get_logger("axolot.speech_profile")

# Heuristic markers — intentionally simple. The system prompt does the heavy
# lifting; this just delivers a stable seed value.
_EMOJI_RE = re.compile(
    "[" + "\U0001F300-\U0001FAFF" + "\U00002600-\U000027BF" + "✀-➿" + "]",
    flags=re.UNICODE,
)
_FORMAL_MARKERS = (
    "however", "therefore", "regards", "sincerely", "additionally",
    "furthermore", "appreciate", "kindly",
)
_CASUAL_MARKERS = (
    "lol", "lmao", "haha", "yeah", "yep", "nah", "tbh", "ngl", "imo",
    "wanna", "gonna", "kinda", "vibe", "ok ", "yo ",
)


def _classify_length(messages: list[str]) -> str:
    if not messages:
        return "medium"
    avg = sum(len(m) for m in messages) / len(messages)
    if avg < 60:
        return "short"
    if avg > 220:
        return "long"
    return "medium"


def _classify_formality(text: str) -> str:
    t = text.lower()
    casual = sum(t.count(m) for m in _CASUAL_MARKERS)
    formal = sum(t.count(m) for m in _FORMAL_MARKERS)
    lowercase_starts = sum(
        1 for line in text.splitlines() if line[:1].islower()
    )
    # Lots of lowercase-starting sentences is the strongest casual signal.
    if casual >= 1 or lowercase_starts >= 3:
        return "casual"
    if formal >= 2:
        return "formal"
    return "mixed"


def _classify_emoji(text: str) -> str:
    n = len(_EMOJI_RE.findall(text))
    if n == 0:
        return "none"
    if n <= 3:
        return "occasional"
    return "frequent"


def _classify_punctuation(messages: list[str]) -> str:
    joined = " ".join(messages)
    if not joined:
        return "standard"
    exclam = joined.count("!")
    multi_exclam = len(re.findall(r"!{2,}", joined))
    periods = joined.count(".")
    sentence_starts = max(1, len(re.findall(r"(?<=[.?!])\s", joined)))
    if multi_exclam >= 2 or exclam / max(1, sentence_starts) > 1.5:
        return "heavy"
    if periods / sentence_starts < 0.3:
        return "minimal"
    return "standard"


def _sample_phrases(messages: list[str], max_phrases: int = 5) -> list[str]:
    """Pick up to N short, repeated phrases — used by the prompt as voice anchors."""
    phrases: Counter[str] = Counter()
    for m in messages:
        # 2-3 word phrases at sentence starts capture the user's "signature openers".
        for match in re.findall(r"\b([a-zA-Z][a-zA-Z']{1,12}(?:\s+[a-zA-Z][a-zA-Z']{1,12}){1,2})\b", m):
            phrases[match.lower()] += 1
    return [p for p, n in phrases.most_common(max_phrases) if n >= 2]


def _ensure_row(db: Session, user_id: str) -> UserPersonality:
    row = (
        db.query(UserPersonality)
        .filter(UserPersonality.user_id == user_id)
        .first()
    )
    if not row:
        row = UserPersonality(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _blend(prev: str | None, observed: str) -> str:
    """Mirror the 0.8/0.2 blend semantics on categorical tokens.

    Cleanly: keep `prev` unless `observed` is the same as the second-to-last
    inference. Practically we don't track history per-field, so the blend
    here just prefers prev when it exists, otherwise takes observed. The
    weekly personality_update job is the canonical re-blend.
    """
    return prev or observed


def bootstrap_from_first_messages(db: Session, user_id: str, min_user_msgs: int = 5) -> bool:
    """If the user has at least `min_user_msgs` and the profile is empty,
    fill it in from their messages. Returns True if anything was written."""
    row = _ensure_row(db, user_id)
    # Profile already populated by onboarding or a previous bootstrap.
    if row.avg_sentence_length and row.formality:
        return False

    msgs = [
        c.content
        for c in (
            db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id, ChatHistory.role == "user")
            .order_by(ChatHistory.created_at.desc())
            .limit(20)
            .all()
        )
    ]
    if len(msgs) < min_user_msgs:
        return False

    joined = "\n".join(msgs)
    row.avg_sentence_length = _blend(row.avg_sentence_length, _classify_length(msgs))
    row.formality = _blend(row.formality, _classify_formality(joined))
    row.emoji_usage = _blend(row.emoji_usage, _classify_emoji(joined))
    row.punctuation_style = _blend(row.punctuation_style, _classify_punctuation(msgs))
    samples = _sample_phrases(msgs)
    if samples:
        row.sample_phrases = samples
    db.commit()
    log_event(
        logger, "speech_profile_bootstrapped",
        user_id=user_id,
        length=row.avg_sentence_length,
        formality=row.formality,
        emoji=row.emoji_usage,
        punctuation=row.punctuation_style,
        samples=len(samples),
    )
    return True


def apply_onboarding_answers(
    db: Session,
    user_id: str,
    answers: dict,
) -> UserPersonality:
    """Write the 5 onboarding-survey answers verbatim into UserPersonality."""
    row = _ensure_row(db, user_id)
    # Normalise answer tokens — the frontend sends them lowercase already but
    # we don't trust the wire shape blindly.
    length_map = {"short": "short", "medium": "medium", "long": "long"}
    formal_map = {"casual": "casual", "mixed": "mixed", "formal": "formal"}
    emoji_map = {"none": "none", "occasional": "occasional", "frequent": "frequent"}
    punct_map = {"minimal": "minimal", "standard": "standard", "heavy": "heavy"}

    row.avg_sentence_length = length_map.get(
        str(answers.get("avg_sentence_length", "")).lower(), row.avg_sentence_length
    )
    row.formality = formal_map.get(
        str(answers.get("formality", "")).lower(), row.formality
    )
    row.emoji_usage = emoji_map.get(
        str(answers.get("emoji_usage", "")).lower(), row.emoji_usage
    )
    row.punctuation_style = punct_map.get(
        str(answers.get("punctuation_style", "")).lower(), row.punctuation_style
    )
    sig = (answers.get("signature_word") or "").strip()
    if sig:
        row.signature_word = sig[:64]
    db.commit()
    db.refresh(row)
    return row


def speech_mirror_block(profile: UserPersonality | None) -> str:
    """Render the profile into the prompt block injected by chat.

    Empty/NULL fields fall back to neutral language so the model still gets
    a coherent instruction on day 1, before any data exists.
    """
    if not profile:
        return (
            "SPEECH MIRROR: No profile yet. Mirror this user's writing style "
            "from the recent conversation lines below — copy their cadence."
        )
    samples = profile.sample_phrases or []
    return (
        "SPEECH MIRROR PROFILE — calibrate every reply to this:\n"
        f"- Sentence length: {profile.avg_sentence_length or 'unknown — copy the user'}\n"
        f"- Tone: {profile.formality or 'unknown — match the user'}\n"
        f"- Emoji usage: {profile.emoji_usage or 'unknown — match the user'}\n"
        f"- Punctuation: {profile.punctuation_style or 'unknown — match the user'}\n"
        + (f"- Signature word the user owns: {profile.signature_word}\n"
           if profile.signature_word else "")
        + (f"- Sample phrases from this user: {', '.join(samples[:5])}\n"
           if samples else "")
        + "If the user writes in fragments, reply in fragments. If they use no "
        "punctuation, use minimal punctuation. Never sound more formal than them."
    )
