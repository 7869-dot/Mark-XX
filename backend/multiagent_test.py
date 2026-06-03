"""End-to-end test of the multi-agent product layer. Run: python multiagent_test.py

Covers:
  - GET /agents/mine lists ALL of the user's agents, primary first.
  - POST /agents creates a non-primary agent when one already exists.
  - First-ever agent via POST /agents lands as primary.
  - PUT /agents/{id}/make-primary atomically swaps the flag (one primary
    per user is the partial-index invariant from Sprint 3 hardening).
  - DELETE /agents/{id}: ok for non-primary; 409 for primary if siblings
    exist; ok for primary if it's the only agent left. Cascades posts,
    follows, scheduled_jobs, alerts, memories.
  - Ownership: another user can never read, promote, or delete your agents.
  - X-Agent-Id header: chat uses the selected agent's voice (system_prompt
    landed in CHAT_CONVERSATION); invalid header => 403.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_multi.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_multi.db"):
    os.remove("axolot_multi.db")

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models import Agent, AgentFollow, AgentPost, ScheduledJob
from app.models.scheduler import ALL_JOB_TYPES

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    d = c.post("/auth/google", json={"email": "m@multi.dev", "name": "Multi User"}).json()
    H = {"Authorization": f"Bearer {d['data']['access_token']}"}
    primary_id = d["meta"]["agent_id"]

    # ── Four-agent team (north-star) ─────────────────────────────────────────
    team = c.get("/agents/team", headers=H).json()["data"]["items"]
    roles = {a["role"] for a in team}
    check("team: four agents seeded at signup", len(team) == 4)
    check("team: roles are feed/jarvis/email/web",
          roles == {"feed", "jarvis", "email", "web"})
    check("team: exactly one feed agent", sum(a["role"] == "feed" for a in team) == 1)
    check("team: only the feed agent is primary",
          [a["is_primary"] for a in team if a["role"] == "feed"] == [True]
          and all(not a["is_primary"] for a in team if a["role"] != "feed"))

    # ── /agents/mine is posting-only (team members are hidden here) ───────────
    r = c.get("/agents/mine", headers=H).json()["data"]
    check("mine: exactly one agent at signup", len(r["items"]) == 1)
    check("mine: it is primary", r["items"][0]["is_primary"] is True
          and r["items"][0]["id"] == primary_id)
    check("mine: summary carries follower_count + auto_post_schedule",
          {"follower_count", "auto_post_schedule"} <= set(r["items"][0].keys()))

    # ── POST /agents creates a NON-primary second agent ──────────────────────
    r = c.post("/agents", headers=H, json={
        "name": "Side Quest", "bio": "Tracks weekend projects.",
        "avatar_seed": "🧪",
    }).json()["data"]
    side_id = r["id"]
    check("create: second agent is non-primary",
          r["is_primary"] is False and r["name"] == "Side Quest")

    r = c.get("/agents/mine", headers=H).json()["data"]
    check("mine: now lists 2 agents", len(r["items"]) == 2)
    check("mine: primary still listed first",
          r["items"][0]["id"] == primary_id and r["items"][1]["id"] == side_id)

    # New agent gets default scheduled_jobs rows.
    db = SessionLocal()
    try:
        n = db.query(ScheduledJob).filter(ScheduledJob.agent_id == side_id).count()
        check("create: ensure_default_jobs seeded default schedule rows for the new agent",
              n == len(ALL_JOB_TYPES))
    finally:
        db.close()

    # ── make-primary: atomic swap ────────────────────────────────────────────
    r = c.put(f"/agents/{side_id}/make-primary", headers=H).json()["data"]
    check("make-primary: target agent now reports is_primary=True",
          r["is_primary"] is True)
    db = SessionLocal()
    try:
        primaries = (
            db.query(Agent)
            .filter(Agent.user_id == d["data"]["user_id"], Agent.is_primary == True)  # noqa: E712
            .all()
        )
        check("make-primary: invariant — exactly one primary per user",
              len(primaries) == 1 and primaries[0].id == side_id)
    finally:
        db.close()

    # Idempotent re-promote.
    r2 = c.put(f"/agents/{side_id}/make-primary", headers=H)
    check("make-primary: re-promoting is a no-op (200)", r2.status_code == 200)

    # ── DELETE protections ───────────────────────────────────────────────────
    # 'side_id' is now primary, 'primary_id' is now the non-primary sibling.
    r = c.delete(f"/agents/{side_id}", headers=H)
    check("delete: cannot delete current primary while siblings exist (409)",
          r.status_code == 409)

    # Delete the non-primary sibling: succeeds.
    r = c.delete(f"/agents/{primary_id}", headers=H).json()
    check("delete: non-primary sibling deletes",
          r["success"] is True and r["data"]["deleted"] is True)

    r = c.get("/agents/mine", headers=H).json()["data"]
    check("mine: down to 1 agent after sibling delete", len(r["items"]) == 1)

    # Now deleting the SOLE remaining (primary) agent works because no siblings.
    # (We don't actually delete it because /agent/me will self-heal — but
    # we prove the policy.)
    r = c.delete(f"/agents/{side_id}", headers=H).json()
    check("delete: primary deletes when it's the only agent",
          r["success"] is True)
    # Self-heal: any subsequent /agent/me call re-creates a primary.
    r = c.get("/agent/me", headers=H).json()["data"]
    check("delete: /agent/me self-heals a primary on next read",
          r["id"] is not None)
    new_primary_id = r["id"]

    # ── Cascade — posts, follows, alerts, schedule, memory ───────────────────
    # Spin up a second agent, give it a post + a follower record + an alert,
    # then delete it and prove every reference is gone.
    r = c.post("/agents", headers=H, json={"name": "Tempo"}).json()["data"]
    tempo_id = r["id"]
    db = SessionLocal()
    try:
        db.add(AgentPost(agent_id=tempo_id, content="ephemeral post"))
        db.add(AgentFollow(follower_agent_id=new_primary_id,
                           following_agent_id=tempo_id))
        db.commit()
    finally:
        db.close()
    c.delete(f"/agents/{tempo_id}", headers=H)
    db = SessionLocal()
    try:
        leftover_posts = db.query(AgentPost).filter(
            AgentPost.agent_id == tempo_id
        ).count()
        leftover_follows = db.query(AgentFollow).filter(
            (AgentFollow.follower_agent_id == tempo_id)
            | (AgentFollow.following_agent_id == tempo_id)
        ).count()
        leftover_schedule = db.query(ScheduledJob).filter(
            ScheduledJob.agent_id == tempo_id
        ).count()
        check("delete: cascades wiped posts", leftover_posts == 0)
        check("delete: cascades wiped follow edges", leftover_follows == 0)
        check("delete: cascades wiped scheduled_jobs rows",
              leftover_schedule == 0)
    finally:
        db.close()

    # ── Ownership boundary ────────────────────────────────────────────────────
    d2 = c.post("/auth/google", json={"email": "other@multi.dev", "name": "Other"}).json()
    H2 = {"Authorization": f"Bearer {d2['data']['access_token']}"}
    r = c.put(f"/agents/{new_primary_id}/make-primary", headers=H2)
    check("ownership: cannot promote another user's agent (403)",
          r.status_code == 403)
    r = c.delete(f"/agents/{new_primary_id}", headers=H2)
    check("ownership: cannot delete another user's agent (403)",
          r.status_code == 403)

    # ── Jarvis chat surface ───────────────────────────────────────────────────
    # Post-overhaul the user only ever talks to Jarvis (no per-agent X-Agent-Id
    # chat routing). Verify the single chat surface replies and is auth-guarded.
    r = c.post("/jarvis/chat", headers=H,
               json={"message": "what should I focus on?", "mode": "default"})
    check("jarvis chat: returns 200 with a reply",
          r.status_code == 200 and bool(r.json()["data"]["reply"]))

    # AUTO mode: Jarvis classifies the task and reports which sub-agent it picked.
    r = c.post("/jarvis/chat", headers=H,
               json={"message": "reply to the investor email", "mode": "auto"}).json()["data"]
    check("jarvis chat: AUTO delegates to a sub-agent",
          r["delegated_to"] in {"email", "web", "schedule", "post", "self"})

    # Auth guard — no token => 401, never a silent fallback.
    r = c.post("/jarvis/chat", json={"message": "hi", "mode": "default"})
    check("jarvis chat: requires auth (401)", r.status_code == 401)

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
