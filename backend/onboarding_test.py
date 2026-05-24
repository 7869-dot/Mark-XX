"""End-to-end test of the 3-step onboarding flow. Run: python onboarding_test.py

Covers: a new user starts un-onboarded, step 1 (name/bio/avatar via PUT
/agent/me), the bio surfacing on the social card, marking onboarding
complete, idempotency, and that the flag rides on GET /agent/me.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_onboard.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_onboard.db"):
    os.remove("axolot_onboard.db")

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    # New sign-up.
    d = c.post("/auth/google", json={"email": "new@axolot.dev", "name": "Nadia New"}).json()
    H = {"Authorization": f"Bearer {d['data']['access_token']}"}
    agent_id = d["meta"]["agent_id"]

    # A brand-new user starts un-onboarded.
    me = c.get("/agent/me", headers=H).json()["data"]
    check("new user starts onboarding_complete=false", me["onboarding_complete"] is False)
    check("agent name defaults from user name", me["name"] == "Nadia's Agent")

    # ── Step 1 — name your agent, add a bio + avatar ───────────────────────────
    r = c.put("/agent/me", headers=H, json={
        "name": "Vera",
        "bio": "Scouts fundraising leads and keeps the calendar honest.",
        "avatar_seed": "\U0001F98E",  # lizard emoji
    }).json()
    check("step 1 updates name", r["data"]["name"] == "Vera")
    check("step 1 stores bio", r["data"]["bio"].startswith("Scouts fundraising"))
    check("step 1 stores avatar_seed", r["data"]["avatar_seed"] == "\U0001F98E")

    # Bio written in onboarding surfaces on the social card.
    card = c.get(f"/agents/{agent_id}/social", headers=H).json()["data"]
    check("onboarding bio surfaces on social card",
          card["bio"].startswith("Scouts fundraising"))

    # ── Step 3 — complete onboarding ───────────────────────────────────────────
    r = c.post("/onboarding/complete", headers=H)
    check("complete returns 200", r.status_code == 200)
    check("complete reports onboarding_complete=true",
          r.json()["data"]["onboarding_complete"] is True)

    me = c.get("/agent/me", headers=H).json()["data"]
    check("flag persists on /agent/me", me["onboarding_complete"] is True)

    # Idempotent — re-running the final step must not error.
    r = c.post("/onboarding/complete", headers=H)
    check("complete is idempotent", r.status_code == 200
          and r.json()["data"]["onboarding_complete"] is True)

    # Unauthenticated calls are rejected.
    r = c.post("/onboarding/complete")
    check("complete requires auth (401)", r.status_code == 401)

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
