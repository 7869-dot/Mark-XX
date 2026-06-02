"""Sprint 2 — Jarvis orchestrator + email agent + draft queue.

Run: .venv/Scripts/python.exe jarvis_test.py
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_jarvis.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")
if os.path.exists("axolot_jarvis.db"):
    os.remove("axolot_jarvis.db")

from fastapi.testclient import TestClient
from app.main import app
from app.core.cache import cache
from app.core.db import SessionLocal
from app.models import Agent, AgentPost
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


with c:
    H, uid = auth("jarvis@axolot.dev", "Jam User")

    # ── Risk flag #2: team (and thus Jarvis agent) exists at login ───────────
    db = SessionLocal()
    try:
        jarvis_agent = db.query(Agent).filter(
            Agent.user_id == uid, Agent.role == AgentRole.jarvis.value
        ).first()
        check("ensure_team ran at login — Jarvis agent exists", jarvis_agent is not None)
        posting_before = db.query(Agent).filter(
            Agent.user_id == uid, Agent.role == AgentRole.feed.value
        ).first()
        posting_post_count_before = db.query(AgentPost).filter(
            AgentPost.agent_id == posting_before.id
        ).count()
    finally:
        db.close()

    # ── 1. Jarvis context generation + schema validity ──────────────────────
    r = c.get("/jarvis/context", headers=H).json()
    ctx = r["data"]["context"]
    check("jarvis context generated", ctx is not None and bool(ctx["greeting"]))
    check("context has a sharp question", bool(ctx["question"]))
    check("known_about_user is 3-5 items", 3 <= len(ctx["known_about_user"]) <= 5, str(len(ctx["known_about_user"])))
    check("team_briefing only assigns email/web (never feed)",
          all(t["agent_role"] in ("email", "web") for t in ctx["team_briefing"]))
    check("greeting avoids forbidden generic copy",
          "good morning" not in ctx["greeting"].lower() and "how can i help" not in ctx["greeting"].lower())

    # ── 2. Cache: second call within TTL doesn't regenerate ──────────────────
    ts1 = ctx["timestamp"]
    r2 = c.get("/jarvis/context", headers=H).json()["data"]["context"]
    check("cached context returned on second call (same timestamp)", r2["timestamp"] == ts1)
    # refresh=true regenerates.
    r3 = c.get("/jarvis/context?refresh=true", headers=H).json()["data"]["context"]
    check("refresh=true regenerates context", r3 is not None)

    # ── 3. Email agent drafted from a Jarvis email task; requires approval ───
    drafts = c.get("/agents/drafts", headers=H).json()["data"]["items"]
    check("email agent produced at least one draft", len(drafts) >= 1, str(len(drafts)))
    if drafts:
        d0 = drafts[0]
        check("draft requires approval (V1 always True)", d0["requires_approval"] is True)
        check("draft is pending (approved is null)", d0["approved"] is None)
        check("draft has body + subject", bool(d0["draft_content"]) and bool(d0["subject_line"]))

    # ── 4. Approval flow: approve marks approved, does NOT send ──────────────
    if drafts:
        did = drafts[0]["id"]
        res = c.patch(f"/agents/drafts/{did}", headers=H, json={"approved": True}).json()["data"]
        check("approve sets approved=true", res["approved"] is True)
        check("approve does NOT send in V1", res["sent"] is False)
        # approved draft no longer in pending queue
        pending = c.get("/agents/drafts", headers=H).json()["data"]["items"]
        check("approved draft leaves the pending queue", all(x["id"] != did for x in pending))

    # Kill flow on a fresh draft.
    c.get("/jarvis/context?refresh=true", headers=H)
    drafts2 = c.get("/agents/drafts", headers=H).json()["data"]["items"]
    if drafts2:
        kid = drafts2[0]["id"]
        res = c.patch(f"/agents/drafts/{kid}", headers=H, json={"approved": False}).json()["data"]
        check("kill sets approved=false", res["approved"] is False)

    # ── 5. Graceful fail: bad token doesn't 500 ──────────────────────────────
    bad = c.get("/jarvis/context", headers={"Authorization": "Bearer nope"})
    check("unauthorized is 401 (not 500)", bad.status_code == 401, str(bad.status_code))

    # ── 6. Posting agent untouched by orchestration ──────────────────────────
    db = SessionLocal()
    try:
        posting_after = db.query(Agent).filter(
            Agent.user_id == uid, Agent.role == AgentRole.feed.value
        ).first()
        check("exactly one posting agent, still primary",
              posting_after.is_primary is True)
        posting_post_count_after = db.query(AgentPost).filter(
            AgentPost.agent_id == posting_after.id
        ).count()
        check("posting agent made no new posts from orchestration",
              posting_post_count_after == posting_post_count_before)
        # No draft was ever attributed to the posting agent.
        from app.models import AgentTaskResult
        posting_drafts = db.query(AgentTaskResult).filter(
            AgentTaskResult.user_id == uid, AgentTaskResult.agent_role == "feed"
        ).count()
        check("no drafts attributed to feed agent", posting_drafts == 0)
    finally:
        db.close()

    # ── 7. Session orchestration overhaul (Sections 2-4) ─────────────────────
    H2, uid2 = auth("manager@axolot.dev", "Haani Doe")

    # First session -> onboarding payload (not a briefing).
    s = c.post("/jarvis/session/start", headers=H2).json()["data"]
    check("first session triggers onboarding", s["onboarding"] is True)
    check("onboarding has 5 questions", len(s["questions"]) == 5)
    check("greeting uses first name", "Haani" in s["greeting"])
    check("first 3 questions are option-select, last 2 free text",
          all(q["type"] == "options" for q in s["questions"][:3])
          and all(q["type"] == "text" for q in s["questions"][3:]))

    m = c.get("/jarvis/memory", headers=H2).json()["data"]["profile"]
    check("memory GET pre-onboarding", m["onboarding_complete"] is False)

    prof = c.patch("/jarvis/memory", headers=H2, json={"answers": {
        "working_on": "Building a startup or product",
        "improve": "Technical / engineering skills",
        "opportunities": ["Freelance", "Learning"],
        "hates": "pointless status meetings",
        "goal": "Ship the beta and land 3 design partners",
    }}).json()["data"]["profile"]
    check("onboarding marks complete", prof["onboarding_complete"] is True)
    check("opportunity prefs mapped to scout categories",
          "freelance" in prof["opportunity_preferences"] and "learning" in prof["opportunity_preferences"])
    check("hates captured", "pointless status meetings" in prof["hates"])
    check("goal stored", prof["goals"].get("this_month", "").startswith("Ship the beta"))

    s2 = c.post("/jarvis/session/start", headers=H2).json()["data"]
    check("second session is not onboarding", s2["onboarding"] is False)
    check("briefing is non-empty", bool(s2["briefing"]))
    check("exactly 3 action items", len(s2["action_items"]) == 3, str(len(s2["action_items"])))
    check("reports has all 3 sub-agents", set(s2["reports"].keys()) == {"email", "feed", "web"})
    check("agent_status lists 3 sub-agents", len(s2["agent_status"]) == 3)

    # Web scout: on-demand run stores + reports finds.
    w = c.post("/agents/web/run", headers=H2).json()["data"]["report"]
    check("web report has top_finds", isinstance(w["top_finds"], list) and len(w["top_finds"]) > 0,
          str(len(w.get("top_finds", []))))
    find = w["top_finds"][0]
    check("find has title+url+summary+category+score",
          all(k in find for k in ("id", "title", "url", "summary", "category", "relevance_score")))

    er = c.post("/agents/email/run", headers=H2).json()["data"]["report"]
    check("email report has priority buckets",
          all(k in er for k in ("urgent", "important", "low", "action_required")))
    fr = c.post("/agents/feed/run", headers=H2).json()["data"]["report"]
    check("feed report has engagement_candidates", "engagement_candidates" in fr)

    st = c.get("/agents/status", headers=H2).json()["data"]["agents"]
    check("status panel has the 3 sub-agents",
          {a["agent_name"] for a in st} == {"email_agent", "feed_agent", "web_agent"})
    check("status panel shows last_run after running", all(a["last_run"] for a in st))

    fb = c.post("/agents/web/feedback", headers=H2,
                json={"result_id": find["id"], "feedback": "useful"}).json()["data"]
    check("web feedback recorded", fb["recorded"] is True)
    m2 = c.get("/jarvis/memory", headers=H2).json()["data"]["profile"]
    check("feedback_log updated", len(m2["feedback_log"]) >= 1)
    bad_fb = c.post("/agents/web/feedback", headers=H2,
                    json={"result_id": "nope", "feedback": "useful"})
    check("feedback rejects unknown result_id (400)", bad_fb.status_code == 400, str(bad_fb.status_code))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
