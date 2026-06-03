"""End-to-end test of the 4-layer memory pipeline. Run: python memory_test.py

Verifies:
  Layer 1 — ChatHistory window (20 turns).
  Layer 2 — ConversationSummary written by the background summarizer.
  Layer 3 — UserPersonality refreshed every 5 user turns.
  Layer 4 — AgentMemory (including post_history) surfaces in the context.
  Builder — build_agent_context returns all keys; build_voice_prompt embeds
            bio + system_prompt + personality + memories.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_mem.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_mem.db"):
    os.remove("axolot_mem.db")

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models import (
    Agent, AgentMemory, ChatHistory, ConversationSummary, User, UserPersonality,
)
from app.models.agent import AgentMemoryType
from app.memory.personality_tracker import refresh_personality_if_due
from app.memory.summarizer import generate_and_store_summary
from app.services.context_builder import (
    CHAT_WINDOW, build_agent_context, build_voice_prompt,
)

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    d = c.post("/auth/google", json={"email": "m@axolot.dev", "name": "Memo User"}).json()
    H = {"Authorization": f"Bearer {d['data']['access_token']}"}
    agent_id = d["meta"]["agent_id"]
    user_id = d["data"]["user_id"]

    # Set a bio + system_prompt so the voice-prompt builder has something to inject.
    c.put("/agent/me", headers=H, json={
        "bio": "Pragmatic strategist who hates fluff.",
    })
    db = SessionLocal()
    try:
        ag = db.query(Agent).filter(Agent.id == agent_id).first()
        ag.system_prompt = "Speak like a chief of staff: terse, decisive."
        db.commit()
    finally:
        db.close()

    # ── Layer 1 — chat history window ────────────────────────────────────────
    # Drive 25 user messages so we comfortably exceed the 20-turn window.
    # Jarvis chat (DEFAULT mode) persists a user + agent turn per call to
    # ChatHistory, which is what the memory pipeline reads.
    for i in range(25):
        c.post("/jarvis/chat", headers=H,
               json={"message": f"Turn {i}: anything new on the Series A?",
                     "mode": "default"})

    db = SessionLocal()
    try:
        total = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).count()
        check("layer1: full chat history persisted",
              total >= 50)  # 25 user + 25 agent turns
        ag = db.query(Agent).filter(Agent.id == agent_id).first()
        ctx = build_agent_context(db, ag)
        # Each turn in chat_text starts with "[user]" or "[agent]" on its own line.
        n_in_ctx = ctx["recent_chats"].count("\n[") + 1 if ctx["recent_chats"] != "No recent conversation." else 0
        check("layer1: context injects exactly CHAT_WINDOW turns",
              n_in_ctx == CHAT_WINDOW)

        # ── Layer 2 — conversation summary written ──────────────────────────
        # The chat route already triggers summarize_user via BackgroundTasks,
        # but BackgroundTasks may not run inside the TestClient context — call
        # the synchronous helper to be deterministic.
        generate_and_store_summary(user_id, db)
        cs = (
            db.query(ConversationSummary)
            .filter(ConversationSummary.user_id == user_id)
            .first()
        )
        check("layer2: ConversationSummary written", cs is not None
              and len(cs.summary) > 0 and cs.message_count >= 50)

        # ── Layer 3 — personality refresh every 5 user turns ───────────────
        # Run the same refresh helper used by the chat BackgroundTask.
        refresh_personality_if_due(user_id)
        up = (
            db.query(UserPersonality)
            .filter(UserPersonality.user_id == user_id)
            .first()
        )
        check("layer3: UserPersonality snapshot exists after 5+ turns",
              up is not None)
        check("layer3: UserPersonality has interests + communication_style",
              up is not None and (up.interests or up.communication_style))

        # ── Layer 4 — agent memory (incl. post_history) ────────────────────
        # Importance 0.8 — above the mined-preference memories that the
        # personality-refresh job sprinkles in (0.65 each), so it lands in
        # the top-6 the builder injects.
        m = AgentMemory(
            agent_id=agent_id,
            memory_type=AgentMemoryType.post_history,
            content="[posted] Trying a sharper morning briefing format.",
            importance_score=0.8,
        )
        db.add(m)
        db.commit()
        ctx = build_agent_context(db, ag)
        check("layer4: post_history memory surfaces in agent_memories",
              "sharper morning briefing" in ctx["agent_memories"])

        # ── Builder — voice prompt assembly ─────────────────────────────────
        vp = build_voice_prompt(db, ag, "Write a one-sentence test post.")
        check("builder: voice prompt includes agent name",
              ag.name in vp)
        check("builder: voice prompt includes bio",
              "Pragmatic strategist" in vp)
        check("builder: voice prompt includes system_prompt",
              "chief of staff" in vp)
        check("builder: voice prompt includes personality vector",
              "openness" in vp and "directness" in vp)
        check("builder: voice prompt includes the instruction",
              "Write a one-sentence test post." in vp)

        # ── Builder — ctx dict carries the new bio + system_prompt fields ──
        check("builder: ctx exposes agent_bio + agent_system_prompt",
              "agent_bio" in ctx and "agent_system_prompt" in ctx
              and ctx["agent_bio"].startswith("Pragmatic"))
        check("builder: ctx exposes conversation_summary",
              "conversation_summary" in ctx and len(ctx["conversation_summary"]) > 0)
    finally:
        db.close()

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
