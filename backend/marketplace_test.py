"""End-to-end test of the agent marketplace. Run: python marketplace_test.py

Covers: idempotent seeding, listing, single-template fetch, 404, clone
applies template to user's existing agent (preserving the user's social
graph), clone_count increments, schedule rows get flipped per capabilities.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_mkt.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_mkt.db"):
    os.remove("axolot_mkt.db")

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models import Agent, AgentTemplate, ScheduledJob
from app.models.scheduler import JOB_AUTO_POST, JOB_INBOX_MONITOR, JOB_MORNING_BRIEFING
from app.services.marketplace import seed_templates

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    # ── Seeded on startup ─────────────────────────────────────────────────────
    items = c.get("/marketplace").json()["data"]["items"]
    check("6 templates seeded by startup", len(items) == 6)
    check("templates carry required fields",
          all(set(t.keys()) >= {"id", "name", "description", "category",
                                 "avatar_seed", "default_schedule",
                                 "capabilities", "clone_count"}
              for t in items))
    categories = {t["category"] for t in items}
    check("all four marketplace categories present",
          {"Productivity", "Social", "Research", "Finance"} <= categories)

    # ── Idempotent seed ──────────────────────────────────────────────────────
    db = SessionLocal()
    try:
        n = seed_templates(db)
        check("re-seeding inserts nothing (idempotent)", n == 0)
    finally:
        db.close()

    # ── Single fetch ─────────────────────────────────────────────────────────
    exec_assistant = next(t for t in items if t["name"] == "Executive Assistant")
    r = c.get(f"/marketplace/{exec_assistant['id']}").json()["data"]
    check("single template fetch round-trips",
          r["name"] == "Executive Assistant"
          and r["capabilities"]["morning_briefing"] is True)
    check("missing template returns 404",
          c.get("/marketplace/does-not-exist").status_code == 404)

    # ── Auth + Clone ─────────────────────────────────────────────────────────
    # Clone requires auth.
    r = c.post(f"/marketplace/{exec_assistant['id']}/clone")
    check("clone requires auth (401)", r.status_code == 401)

    d = c.post("/auth/google", json={"email": "mkt@axolot.dev", "name": "Marketplace User"}).json()
    H = {"Authorization": f"Bearer {d['data']['access_token']}"}
    original_agent_id = d["meta"]["agent_id"]

    # ── Preview endpoint ────────────────────────────────────────────────────
    pv = c.get(f"/marketplace/{exec_assistant['id']}/clone/preview", headers=H).json()["data"]
    check("preview returns current+after+warning shape",
          set(pv.keys()) >= {"current", "after", "warning", "template"})
    check("preview current matches the user's agent",
          pv["current"]["name"] is not None)
    check("preview after matches the template",
          pv["after"]["name"] == "Executive Assistant"
          and pv["after"]["auto_post_schedule"] == "off")

    # ── Clone without confirm => 409 with preview payload ──────────────────
    r = c.post(f"/marketplace/{exec_assistant['id']}/clone", headers=H)
    check("clone without confirmation => 409", r.status_code == 409)
    body = r.json()
    check("409 body carries error code 'confirm_required'",
          body.get("error") == "confirm_required")
    check("409 body carries the same preview payload",
          body.get("preview", {}).get("after", {}).get("name") == "Executive Assistant")

    # Empty-body POST also rejected.
    r = c.post(f"/marketplace/{exec_assistant['id']}/clone", headers=H, json={})
    check("clone with empty body => 409", r.status_code == 409)

    # ── Confirmed clone applies ────────────────────────────────────────────
    r = c.post(
        f"/marketplace/{exec_assistant['id']}/clone",
        headers=H, json={"confirmed": True},
    ).json()["data"]
    cloned = r["agent"]
    check("clone preserves agent id (re-themes, never duplicates)",
          cloned["id"] == original_agent_id)
    check("clone applies template name",
          cloned["name"] == "Executive Assistant")
    check("clone applies template bio + avatar",
          cloned["bio"].startswith("Manages your email")
          and cloned["avatar_seed"] == exec_assistant["avatar_seed"])

    # Schedule rows flipped per capabilities.
    db = SessionLocal()
    try:
        rows = {
            r.job_type: r
            for r in db.query(ScheduledJob)
            .filter(ScheduledJob.agent_id == original_agent_id)
            .all()
        }
        check("clone enables morning_briefing per capabilities",
              rows[JOB_MORNING_BRIEFING].enabled is True)
        check("clone enables inbox_monitor per capabilities",
              rows[JOB_INBOX_MONITOR].enabled is True)
        check("Executive Assistant default_schedule=off => auto_post off",
              rows[JOB_AUTO_POST].enabled is False)

        # system_prompt landed.
        ag = db.query(Agent).filter(Agent.id == original_agent_id).first()
        check("clone stamps system_prompt onto the agent",
              ag.system_prompt and "executive assistant" in ag.system_prompt.lower())
    finally:
        db.close()

    # clone_count incremented.
    r2 = c.get(f"/marketplace/{exec_assistant['id']}").json()["data"]
    check("clone_count incremented",
          r2["clone_count"] == exec_assistant["clone_count"] + 1)

    # ── Clone a daily-poster template — auto_post flips to daily ──────────────
    journal = next(t for t in items if t["name"] == "Personal Journal")
    c.post(f"/marketplace/{journal['id']}/clone",
           headers=H, json={"confirmed": True})
    db = SessionLocal()
    try:
        ag = db.query(Agent).filter(Agent.id == original_agent_id).first()
        check("second clone re-themes again (Personal Journal)",
              ag.name == "Personal Journal" and ag.auto_post_schedule == "daily")
        row = (
            db.query(ScheduledJob)
            .filter(ScheduledJob.agent_id == original_agent_id,
                    ScheduledJob.job_type == JOB_AUTO_POST)
            .first()
        )
        check("auto_post scheduled_job enabled when default_schedule=daily",
              row.enabled is True and row.cron_expr == "daily")
    finally:
        db.close()

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
