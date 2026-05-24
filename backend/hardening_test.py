"""End-to-end test of the hardening sprint. Run: python hardening_test.py

Covers:
  Fix 1 — scheduler sweeps stamp last_error / last_error_at on a failure,
          surface a system_notice AgentPost on a Gemini transient, and never
          let one agent's exception abort the rest of the sweep.
  Fix 2 — marketplace preview endpoint + 409 on unconfirmed clone.
  Fix 3 — Agent.is_primary defaults to True; the partial unique index
          forbids two is_primary=TRUE rows per user; get_primary_agent
          helper returns the primary; user.agent relationship still works
          when secondaries exist.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_harden.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_harden.db"):
    os.remove("axolot_harden.db")

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.db import SessionLocal
from app.models import (
    Agent, AgentPost, ScheduledJob, User,
)
from app.models.scheduler import (
    JOB_AUTO_POST, JOB_INBOX_MONITOR, JOB_MORNING_BRIEFING,
)
from app.scheduler.proactive_jobs import (
    auto_post_sweep, inbox_monitor_sweep, morning_briefing_post,
)
from app.services.agent_service import create_agent_for_user, get_primary_agent

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    # Two users: one will see a failure, one won't, so we can prove the loop
    # doesn't abort when a single agent throws.
    d_a = c.post("/auth/google", json={"email": "a@harden.dev", "name": "Alice"}).json()
    d_b = c.post("/auth/google", json={"email": "b@harden.dev", "name": "Bob"}).json()
    H_a = {"Authorization": f"Bearer {d_a['data']['access_token']}"}
    H_b = {"Authorization": f"Bearer {d_b['data']['access_token']}"}
    agent_a = d_a["meta"]["agent_id"]
    agent_b = d_b["meta"]["agent_id"]

    # Connect Gmail for both so morning_briefing is allowed to run.
    for H in (H_a, H_b):
        auth_url = c.post("/integrations/gmail/connect", headers=H).json()["data"]["authorization_url"]
        c.get(auth_url.replace("http://testserver", ""), headers=H)

    # ── Fix 3 — is_primary defaults + partial unique ─────────────────────────
    db = SessionLocal()
    try:
        ag_a = db.query(Agent).filter(Agent.id == agent_a).first()
        check("Fix3: create_agent_for_user sets is_primary=True",
              ag_a.is_primary is True)

        # get_primary_agent finds the primary.
        found = get_primary_agent(db, ag_a.user_id)
        check("Fix3: get_primary_agent returns the primary agent",
              found is not None and found.id == agent_a)

        # Adding a SECOND is_primary=True agent for the same user must fail.
        rogue = Agent(user_id=ag_a.user_id, is_primary=True, name="Rogue Primary")
        db.add(rogue)
        try:
            db.commit()
            check("Fix3: two is_primary=TRUE rows per user => IntegrityError", False)
        except IntegrityError:
            db.rollback()
            check("Fix3: two is_primary=TRUE rows per user => IntegrityError", True)

        # A non-primary second agent for the SAME user IS allowed — proves the
        # legacy UNIQUE(user_id) is really gone.
        secondary = Agent(
            user_id=ag_a.user_id, is_primary=False, name="Side Agent",
        )
        db.add(secondary)
        db.commit()
        secondary_id = secondary.id
        check("Fix3: secondary (is_primary=False) agent persists for same user",
              secondary_id is not None)

        # user.agent relationship still resolves to the primary even with a
        # secondary in the same user's collection.
        u_a = db.query(User).filter(User.id == ag_a.user_id).first()
        # Force refresh so the new secondary lands in the session.
        db.refresh(u_a)
        check("Fix3: user.agent returns the primary, not the secondary",
              u_a.agent is not None and u_a.agent.id == agent_a)
        check("Fix3: user.agents collection includes both",
              {a.id for a in u_a.agents} >= {agent_a, secondary_id})

        # Tidy up the secondary so it doesn't perturb later sweeps.
        db.delete(secondary)
        db.commit()
    finally:
        db.close()

    # ── Fix 1 — error stamping + system_notice ──────────────────────────────
    # Force generate_for_agent to raise a "quota"-like exception. The sweep
    # must (a) stamp last_error on agent A's row, (b) continue and post for
    # agent B if it would have, (c) leave a system_notice post for A.
    class FakeQuota(Exception):
        pass

    def boom_quota(db, agent, instruction, response_format="text"):
        raise FakeQuota("429 quota exceeded — try again later")

    # Run morning_briefing under the fault injection.
    db = SessionLocal()
    try:
        posts_before_a = db.query(AgentPost).filter(AgentPost.agent_id == agent_a).count()
    finally:
        db.close()

    with patch(
        "app.scheduler.proactive_jobs.generate_for_agent",
        side_effect=boom_quota,
    ):
        morning_briefing_post()

    db = SessionLocal()
    try:
        row_a = (
            db.query(ScheduledJob)
            .filter(ScheduledJob.agent_id == agent_a,
                    ScheduledJob.job_type == JOB_MORNING_BRIEFING)
            .first()
        )
        check("Fix1: failed sweep stamps last_error on scheduled_jobs row",
              row_a.last_error is not None and "quota" in row_a.last_error.lower())
        check("Fix1: failed sweep stamps last_error_at",
              isinstance(row_a.last_error_at, datetime))

        # Gemini transient => system_notice post recorded.
        notices = (
            db.query(AgentPost)
            .filter(AgentPost.agent_id == agent_a,
                    AgentPost.post_type == "system_notice")
            .all()
        )
        check("Fix1: Gemini transient surfaces a system_notice post",
              len(notices) >= 1
              and "temporary error" in notices[0].content.lower())

        # No regular standard post should have been written for A this run.
        posts_after_a = db.query(AgentPost).filter(
            AgentPost.agent_id == agent_a,
            AgentPost.post_type == "standard",
        ).count()
        check("Fix1: no standard post written when sweep failed",
              posts_after_a == 0)
    finally:
        db.close()

    # Now prove a non-Gemini exception still records last_error but does NOT
    # write a system_notice (we only degrade with a notice on Gemini transients).
    db = SessionLocal()
    try:
        # Clear A's row so we can detect a fresh write.
        row_a = db.query(ScheduledJob).filter(
            ScheduledJob.agent_id == agent_a,
            ScheduledJob.job_type == JOB_INBOX_MONITOR,
        ).first()
        row_a.last_error = None
        row_a.last_error_at = None
        db.commit()
    finally:
        db.close()

    def boom_generic(db, agent, instruction, response_format="text"):
        raise RuntimeError("totally unrelated failure")

    with patch(
        "app.scheduler.proactive_jobs.generate_for_agent",
        side_effect=boom_generic,
    ):
        inbox_monitor_sweep()

    db = SessionLocal()
    try:
        row_a = db.query(ScheduledJob).filter(
            ScheduledJob.agent_id == agent_a,
            ScheduledJob.job_type == JOB_INBOX_MONITOR,
        ).first()
        check("Fix1: non-Gemini failure still stamps last_error",
              row_a.last_error is not None and "RuntimeError" in row_a.last_error)
        # No NEW system notice from this generic failure path.
        notices = (
            db.query(AgentPost)
            .filter(AgentPost.agent_id == agent_a,
                    AgentPost.post_type == "system_notice")
            .count()
        )
        check("Fix1: non-Gemini failure does NOT write a system_notice",
              notices == 1)  # still only the one from the earlier quota run
    finally:
        db.close()

    # Loop continues across agents: inject a failure ONLY for agent A.
    real_gen = None
    from app.scheduler import proactive_jobs as pj_mod
    real_gen = pj_mod.generate_for_agent

    calls: list[str] = []

    def selective_boom(db, agent, instruction, response_format="text"):
        calls.append(agent.id)
        if agent.id == agent_a:
            raise FakeQuota("503 service unavailable")
        return real_gen(db, agent, instruction, response_format)

    # Enable auto_post=daily for both A and B so both are visited.
    c.put(f"/agents/{agent_a}/schedule", headers=H_a, json={"auto_post": "daily"})
    c.put(f"/agents/{agent_b}/schedule", headers=H_b, json={"auto_post": "daily"})

    db = SessionLocal()
    try:
        b_posts_before = db.query(AgentPost).filter(
            AgentPost.agent_id == agent_b, AgentPost.post_type == "standard"
        ).count()
    finally:
        db.close()

    with patch(
        "app.scheduler.proactive_jobs.generate_for_agent",
        side_effect=selective_boom,
    ):
        auto_post_sweep()

    db = SessionLocal()
    try:
        b_posts_after = db.query(AgentPost).filter(
            AgentPost.agent_id == agent_b, AgentPost.post_type == "standard"
        ).count()
        check("Fix1: one agent's failure does NOT abort the sweep for others",
              b_posts_after > b_posts_before)
        # A also got a system_notice this time around (auto_post quota error).
        a_notices = db.query(AgentPost).filter(
            AgentPost.agent_id == agent_a, AgentPost.post_type == "system_notice"
        ).count()
        check("Fix1: failed agent still gets its system_notice on quota error",
              a_notices >= 2)
    finally:
        db.close()

    # ── Fix 2 — marketplace preview + confirm ────────────────────────────────
    templates = c.get("/marketplace").json()["data"]["items"]
    t = templates[0]

    pv = c.get(f"/marketplace/{t['id']}/clone/preview", headers=H_a).json()["data"]
    check("Fix2: preview shape includes current/after/warning/template",
          set(pv.keys()) >= {"current", "after", "warning", "template"})
    check("Fix2: preview 'after' matches the template",
          pv["after"]["name"] == t["name"])

    r = c.post(f"/marketplace/{t['id']}/clone", headers=H_a)
    check("Fix2: unconfirmed clone returns 409", r.status_code == 409)
    body = r.json()
    check("Fix2: 409 body carries preview payload",
          body.get("preview", {}).get("after", {}).get("name") == t["name"])
    check("Fix2: 409 message mentions confirmation",
          "confirm" in (body.get("message") or "").lower())

    r = c.post(f"/marketplace/{t['id']}/clone", headers=H_a,
               json={"confirmed": True}).json()
    check("Fix2: confirmed clone succeeds",
          r["success"] is True and r["data"]["agent"]["name"] == t["name"])

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
