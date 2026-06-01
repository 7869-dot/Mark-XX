"""Sprint 3A — Jarvis chat command modes (default/email/schedule/research/post).

Run: .venv/Scripts/python.exe jarvis_chat_test.py
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_jchat.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")
if os.path.exists("axolot_jchat.db"):
    os.remove("axolot_jchat.db")

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models import Agent, AgentPost, ChatHistory, PostDraft
from app.models.agent import AgentRole

c = TestClient(app)
ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra and not cond else ""))
    ok = ok and bool(cond)


def auth(email, name):
    d = c.post("/auth/google", json={"email": email, "name": name}).json()
    return {"Authorization": f"Bearer {d['data']['access_token']}"}, d["data"]["user_id"]


def chat(H, message, mode="default"):
    return c.post("/jarvis/chat", headers=H, json={"message": message, "mode": mode}).json()["data"]


with c:
    H, uid = auth("jchat@axolot.dev", "Chat User")
    c.put("/agent/me", headers=H, json={"name": "Axo", "goals": ["Ship"], "onboarded": {"completed": True}})

    db = SessionLocal()
    posting = db.query(Agent).filter(Agent.user_id == uid, Agent.role == AgentRole.posting.value).first()
    posts_before = db.query(AgentPost).filter(AgentPost.agent_id == posting.id).count()
    db.close()

    # ── DEFAULT ──────────────────────────────────────────────────────────────
    r = chat(H, "I keep putting off the rewrite. talk me through it.")
    check("default: reply present, no action", bool(r["reply"]) and r["action"] is None and r["mode"] == "default")

    # ── EMAIL ────────────────────────────────────────────────────────────────
    r = chat(H, "Follow up with the guy from Tuesday's meeting", "email")
    check("email: produces draft_email action", r["action"] and r["action"]["type"] == "draft_email", str(r.get("action")))
    check("email: action requires approval", r["action"]["requires_approval"] is True)
    check("email: jarvis speaks in reply", bool(r["reply"]))
    drafts = c.get("/agents/drafts", headers=H).json()["data"]["items"]
    check("email: draft landed in agent_task_results", len(drafts) >= 1)
    check("email: draft requires approval (V1)", all(d["requires_approval"] for d in drafts))

    # ── SCHEDULE ─────────────────────────────────────────────────────────────
    r = chat(H, "Schedule a call with Priya on Friday", "schedule")
    check("schedule: produces schedule_event action", r["action"] and r["action"]["type"] == "schedule_event", str(r.get("action")))
    check("schedule: requires approval", r["action"]["requires_approval"] is True)
    sdrafts = c.get("/agents/schedule-drafts", headers=H).json()["data"]["items"]
    check("schedule: draft landed in schedule_drafts", len(sdrafts) >= 1)
    sid = sdrafts[0]["id"]
    dec = c.patch(f"/agents/schedule-drafts/{sid}", headers=H, json={"approved": True}).json()["data"]
    check("schedule: approve does NOT book (V1)", dec["approved"] is True and dec["booked"] is False)

    # ── RESEARCH ─────────────────────────────────────────────────────────────
    r = chat(H, "What's the state of small language models?", "research")
    check("research: returns research_result action", r["action"] and r["action"]["type"] == "research_result")
    check("research: no approval needed", r["action"]["requires_approval"] is False)
    p = r["action"]["payload"]
    check("research: has synthesis + key_points + sources + follow_ups",
          bool(p["synthesis"]) and len(p["key_points"]) >= 1 and "sources" in p and len(p["follow_up_questions"]) >= 1)
    check("research: follow_up surfaced", bool(r["follow_up"]))

    # ── POST ─────────────────────────────────────────────────────────────────
    r = chat(H, "I want to post about shipping beating polishing", "post")
    check("post: produces post_draft action", r["action"] and r["action"]["type"] == "post_draft", str(r.get("action")))
    check("post: requires approval", r["action"]["requires_approval"] is True)
    pdrafts = c.get("/agents/post-drafts", headers=H).json()["data"]["items"]
    check("post: draft landed in post_drafts", len(pdrafts) >= 1)

    # ── post_drafts is NOT the social layer; posting agent unaffected ────────
    feed = c.get("/feed?ranked=false", headers=H).json()["data"]["items"]
    pd_content = pdrafts[0]["content"]
    check("post: draft is NOT in the public feed", all(it["content"] != pd_content for it in feed))
    db = SessionLocal()
    posts_after = db.query(AgentPost).filter(AgentPost.agent_id == posting.id).count()
    check("posting agent made no new posts from chat modes", posts_after == posts_before)
    db.close()

    # ── chat history persisted (with mode), feeds memory ─────────────────────
    db = SessionLocal()
    rows = db.query(ChatHistory).filter(ChatHistory.user_id == uid).all()
    modes = {r.mode for r in rows if r.mode}
    check("chat history persisted with mode tags",
          {"default", "email", "schedule", "research", "post"} <= modes, str(modes))
    check("each mode wrote a user + agent turn",
          sum(1 for r in rows if r.mode == "email") == 2)
    db.close()

    # ── auth guard ───────────────────────────────────────────────────────────
    bad = c.post("/jarvis/chat", json={"message": "hi", "mode": "default"})
    check("chat requires auth (401)", bad.status_code == 401)

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
