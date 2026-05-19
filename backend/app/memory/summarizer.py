"""ConversationSummary writer — the previously-missing 4th memory layer.

ChatHistory (raw turns) is compressed here into one rolling ConversationSummary
row per user. context_builder.py already reads ConversationSummary; this module
is what finally populates it.
"""
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import ChatHistory, ConversationSummary
from app.services import gemini

logger = get_logger("axolot.summarizer")

WINDOW = 20          # most-recent turns fed to the compressor
MIN_MESSAGES = 10    # below this there isn't enough signal to summarize

SUMMARY_PROMPT = """You are a memory compression engine. Given a conversation \
history between a user and their AI agent, produce a concise summary (max 150 \
words) capturing:
- The user's current goals and priorities
- Key facts the agent should remember long-term
- Any decisions or preferences expressed
Return only the summary. No preamble.

Conversation history:
{history}
"""


def generate_and_store_summary(user_id: str, db: Session) -> str | None:
    """Compress this user's recent chat into a single rolling summary row.

    Returns the summary text, or None if skipped (too few messages).
    Upserts: one ConversationSummary per user — updated in place, never duped.
    """
    total = (
        db.query(ChatHistory).filter(ChatHistory.user_id == user_id).count()
    )
    if total < MIN_MESSAGES:
        log_event(logger, "summary_skipped_few_messages",
                  user_id=user_id, count=total)
        return None

    recent = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(WINDOW)
        .all()
    )
    recent.reverse()  # chronological
    transcript = "\n".join(f"[{m.role}] {m.content}" for m in recent)

    summary = (
        gemini.generate(
            SUMMARY_PROMPT.format(history=transcript), response_format="text"
        )
        or ""
    ).strip()
    if not summary:
        log_event(logger, "summary_empty", user_id=user_id)
        return None

    row = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user_id)
        .order_by(ConversationSummary.created_at.desc())
        .first()
    )
    if row is None:
        row = ConversationSummary(user_id=user_id)
        db.add(row)
    row.summary = summary
    row.message_count = total
    # Bump timestamp so context_builder's "newest first" ordering surfaces it.
    from datetime import datetime

    row.created_at = datetime.utcnow()
    db.commit()

    log_event(logger, "summary_stored", user_id=user_id,
              message_count=total, chars=len(summary))
    return summary


def summarize_user(user_id: str) -> None:
    """BackgroundTask entrypoint — owns its own DB session (request session is
    already closed by the time this runs)."""
    db = SessionLocal()
    try:
        generate_and_store_summary(user_id, db)
    except Exception as exc:  # noqa: BLE001 — background work must never crash
        log_event(logger, "summary_failed", user_id=user_id, error=str(exc))
    finally:
        db.close()
