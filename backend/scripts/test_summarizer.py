"""Manual check for the ConversationSummary writer.

Seeds 15 fake chat turns for a throwaway user, runs the summarizer, and
confirms a row was persisted. Run from backend/:  python scripts/test_summarizer.py
"""
import os
import sys

os.environ.setdefault("USE_STUBS", "true")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import Base, engine, SessionLocal  # noqa: E402
import app.models  # noqa: F401,E402  (populate metadata)
from app.models import User, ChatHistory, ConversationSummary  # noqa: E402
from app.memory.summarizer import generate_and_store_summary  # noqa: E402

Base.metadata.create_all(bind=engine)
db = SessionLocal()

TEST_EMAIL = "summarizer-test@stub.axolot.dev"

# Clean any prior run.
old = db.query(User).filter(User.email == TEST_EMAIL).first()
if old:
    db.query(ChatHistory).filter(ChatHistory.user_id == old.id).delete()
    db.query(ConversationSummary).filter(
        ConversationSummary.user_id == old.id
    ).delete()
    db.delete(old)
    db.commit()

user = User(email=TEST_EMAIL, name="Summarizer Test")
db.add(user)
db.commit()
db.refresh(user)

seed = [
    "I'm trying to raise a $3M seed round by Q3.",
    "Got it — fundraising is the top priority. I'll track investor outreach.",
    "Also I want to ship the v2 onboarding before the raise.",
    "Noted. v2 onboarding is a pre-raise milestone.",
    "Prefer concise updates, no fluff.",
    "Understood — I'll keep updates terse and signal-only.",
    "Met an investor at Northstar, follow up Thursday.",
    "I'll prep a follow-up for the Northstar contact for Thursday.",
    "Don't schedule anything before 10am, that's deep work.",
    "Recorded — mornings before 10am are protected focus time.",
    "We decided to drop the mobile app for now.",
    "Decision logged: mobile app deprioritized.",
    "Main metric I care about is activation rate.",
    "Tracking activation rate as your north-star metric.",
    "Remind me to send the data room link to Northstar.",
]
for i, content in enumerate(seed):
    db.add(ChatHistory(
        user_id=user.id,
        role="user" if i % 2 == 0 else "agent",
        content=content,
    ))
db.commit()

print(f"Seeded {db.query(ChatHistory).filter(ChatHistory.user_id == user.id).count()} messages.\n")

summary = generate_and_store_summary(user.id, db)
print("Returned summary:\n", summary, "\n")

stored = (
    db.query(ConversationSummary)
    .filter(ConversationSummary.user_id == user.id)
    .all()
)
print(f"ConversationSummary rows for user: {len(stored)} (expect exactly 1)")
if stored:
    r = stored[0]
    print(f"  message_count = {r.message_count}")
    print(f"  summary stored = {bool(r.summary)}")

# Idempotency: a second run must UPDATE, not insert a duplicate.
generate_and_store_summary(user.id, db)
again = (
    db.query(ConversationSummary)
    .filter(ConversationSummary.user_id == user.id)
    .count()
)
print(f"After 2nd run, rows = {again} (expect still 1 — upsert, no dupes)")

db.close()
