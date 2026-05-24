"""End-to-end test of the proactive scheduler. Run: python scheduler_test.py

Covers:
- Defaults seeded on agent creation (briefing+monitor on, auto_post off).
- GET /agents/{id}/schedule + PUT toggles.
- Ownership: cannot toggle another user's agent.
- morning_briefing_post — posts to feed only if an integration is connected.
- inbox_monitor_sweep — alerts on urgent/VIP, idempotent (no double-alert).
- auto_post_sweep — fires daily/weekly per agent.auto_post_schedule.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_sched.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_sched.db"):
    os.remove("axolot_sched.db")

from datetime import datetime

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models import (
    Agent, AgentAlert, AgentPost, ScheduledJob, User,
)
from app.models.scheduler import (
    JOB_AUTO_POST, JOB_INBOX_MONITOR, JOB_MORNING_BRIEFING,
)
from app.scheduler.proactive_jobs import (
    auto_post_sweep, inbox_monitor_sweep, morning_briefing_post,
)

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    # Register a user (auto-creates an agent + default schedule rows).
    d = c.post("/auth/google", json={"email": "sch@axolot.dev", "name": "Scheduler User"}).json()
    H = {"Authorization": f"Bearer {d['data']['access_token']}"}
    agent_id = d["meta"]["agent_id"]

    # ── Defaults seeded ────────────────────────────────────────────────────────
    s = c.get(f"/agents/{agent_id}/schedule", headers=H).json()["data"]
    jobs = {j["job_type"]: j for j in s["jobs"]}
    check("3 default schedule rows seeded", set(jobs.keys()) ==
          {JOB_MORNING_BRIEFING, JOB_INBOX_MONITOR, JOB_AUTO_POST})
    check("morning_briefing enabled by default",
          jobs[JOB_MORNING_BRIEFING]["enabled"] is True)
    check("inbox_monitor enabled by default",
          jobs[JOB_INBOX_MONITOR]["enabled"] is True)
    check("auto_post disabled by default",
          jobs[JOB_AUTO_POST]["enabled"] is False and s["auto_post_schedule"] == "off")

    # ── PUT toggles ────────────────────────────────────────────────────────────
    r = c.put(f"/agents/{agent_id}/schedule", headers=H,
              json={"morning_briefing": False, "auto_post": "daily"}).json()["data"]
    jobs = {j["job_type"]: j for j in r["jobs"]}
    check("PUT disables morning_briefing",
          jobs[JOB_MORNING_BRIEFING]["enabled"] is False)
    check("PUT enables auto_post=daily",
          jobs[JOB_AUTO_POST]["enabled"] is True and r["auto_post_schedule"] == "daily")
    check("inbox_monitor untouched by partial update",
          jobs[JOB_INBOX_MONITOR]["enabled"] is True)

    # ── Ownership ─────────────────────────────────────────────────────────────
    d2 = c.post("/auth/google", json={"email": "other@axolot.dev", "name": "Other"}).json()
    H2 = {"Authorization": f"Bearer {d2['data']['access_token']}"}
    r = c.get(f"/agents/{agent_id}/schedule", headers=H2)
    check("cannot view another user's schedule (403)", r.status_code == 403)
    r = c.put(f"/agents/{agent_id}/schedule", headers=H2, json={"auto_post": "off"})
    check("cannot toggle another user's schedule (403)", r.status_code == 403)

    # ── Connect Gmail+Calendar so the integration-gated behaviors fire ────────
    auth_url = c.post(
        "/integrations/gmail/connect", headers=H,
    ).json()["data"]["authorization_url"]
    c.get(auth_url.replace("http://testserver", ""), headers=H)  # stub callback

    # Re-enable morning briefing for the firing test.
    c.put(f"/agents/{agent_id}/schedule", headers=H,
          json={"morning_briefing": True, "auto_post": "daily"})

    db = SessionLocal()
    try:
        # ── Morning briefing fires & posts ────────────────────────────────────
        before = db.query(AgentPost).filter(AgentPost.agent_id == agent_id).count()
        morning_briefing_post()
        after = db.query(AgentPost).filter(AgentPost.agent_id == agent_id).count()
        check("morning_briefing posts to feed", after > before)
        row = (
            db.query(ScheduledJob)
            .filter(ScheduledJob.agent_id == agent_id,
                    ScheduledJob.job_type == JOB_MORNING_BRIEFING)
            .first()
        )
        check("morning_briefing last_run stamped", row.last_run is not None)

        # ── Inbox monitor alerts & dedupes ────────────────────────────────────
        before = db.query(AgentAlert).filter(AgentAlert.agent_id == agent_id).count()
        inbox_monitor_sweep()
        after = db.query(AgentAlert).filter(AgentAlert.agent_id == agent_id).count()
        check("inbox_monitor created at least one alert", after > before)
        first_count = after
        # Re-run — no new alerts, message_ids already recorded.
        inbox_monitor_sweep()
        after2 = db.query(AgentAlert).filter(AgentAlert.agent_id == agent_id).count()
        check("inbox_monitor dedupes — same message never alerted twice",
              after2 == first_count)

        # ── Auto-post fires ───────────────────────────────────────────────────
        before = db.query(AgentPost).filter(AgentPost.agent_id == agent_id).count()
        auto_post_sweep()
        after = db.query(AgentPost).filter(AgentPost.agent_id == agent_id).count()
        check("auto_post (daily) posts to feed", after > before)

        # ── auto_post=off => job no-ops ──────────────────────────────────────
        c.put(f"/agents/{agent_id}/schedule", headers=H, json={"auto_post": "off"})
        before = db.query(AgentPost).filter(AgentPost.agent_id == agent_id).count()
        auto_post_sweep()
        after = db.query(AgentPost).filter(AgentPost.agent_id == agent_id).count()
        check("auto_post=off => sweep skips this agent", before == after)
    finally:
        db.close()

    # ── Schedule survives restart (rows persist) ──────────────────────────────
    s = c.get(f"/agents/{agent_id}/schedule", headers=H).json()["data"]
    jobs = {j["job_type"]: j for j in s["jobs"]}
    check("schedule rows persist across reads",
          jobs[JOB_AUTO_POST]["enabled"] is False
          and jobs[JOB_INBOX_MONITOR]["enabled"] is True)

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
