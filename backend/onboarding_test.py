"""End-to-end test of new-user onboarding + cold-start feed (Sprints 1-4).

Run: .venv/Scripts/python.exe onboarding_test.py

Covers: a new user starts un-onboarded; the cold-start feed is pre-warmed with
Featured posts from the seed persona agents; the Step-3 orchestration endpoints
(persona → bio → autopost → run-a2a); PUT /users/me + /users/me/onboarding-complete;
the flag riding on GET /agent/me; idempotency; and Featured injection stopping
once the user follows a real (non-seed) agent.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_onboard.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "true")  # we WANT the welcome agents

if os.path.exists("axolot_onboard.db"):
    os.remove("axolot_onboard.db")

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra and not cond else ""))
    ok = ok and bool(cond)


def auth(email, name):
    d = c.post("/auth/google", json={"email": email, "name": name}).json()
    return {"Authorization": f"Bearer {d['data']['access_token']}"}, d["meta"]["agent_id"]


with c:  # lifespan startup seeds Ada/Bram/Cara
    # Seed personas exist on the network.
    sysh, _ = auth("scout@axolot.dev", "Scout")
    disc = c.get("/social/discover?limit=20", headers=sysh).json()["data"]
    check("seed personas exist (Ada/Bram/Cara)",
          {"Ada", "Bram", "Cara"} <= {d["name"] for d in disc},
          str({d["name"] for d in disc}))

    # New sign-up.
    H, agent_id = auth("new@axolot.dev", "Nadia New")
    me = c.get("/agent/me", headers=H).json()["data"]
    check("new user starts onboarding_complete=false", me["onboarding_complete"] is False)
    check("agent name defaults from user name", me["name"] == "Nadia's Agent")

    # Cold-start feed is pre-warmed with Featured persona posts.
    feed = c.get("/feed?ranked=true", headers=H).json()["data"]
    check("new-user feed is non-empty", len(feed["items"]) >= 1, str(len(feed["items"])))
    check("feed reports featured_count >= 1", feed.get("featured_count", 0) >= 1,
          str(feed.get("featured_count")))
    featured = [it for it in feed["items"] if it.get("is_featured")]
    check("featured posts come from seed personas",
          featured and all(it["author_name"] in {"Ada", "Bram", "Cara"} for it in featured),
          str([it["author_name"] for it in featured]))

    # ── Step 1 — name + interests (persona) via PUT /agent/me ───────────────
    r = c.put("/agent/me", headers=H, json={
        "name": "Vera",
        "voice_tone": "analytical",
        "posting_style": "long threads",
        "core_interests": ["AI", "startups", "design"],
        "interest_tags": ["AI", "startups", "design"],
        "avatar_seed": "\U0001F98E",
    }).json()
    check("step 1 updates name", r["data"]["name"] == "Vera")
    check("step 1 sets voice_tone", r["data"]["voice_tone"] == "analytical")
    check("step 1 sets core_interests", r["data"]["core_interests"] == ["AI", "startups", "design"])

    # ── Step 3 — orchestration: bio → first post → A2A scan ─────────────────
    bio = c.post(f"/agents/{agent_id}/generate-bio", headers=H).json()["data"]["bio"]
    check("onboarding generated a bio", bool(bio.strip()))
    card = c.get(f"/agents/{agent_id}/social", headers=H).json()["data"]
    check("generated bio surfaces on social card", card["bio"] == bio)

    post = c.post(f"/agents/{agent_id}/autopost", headers=H).json()["data"]
    check("onboarding made the first post", bool(post["content"].strip()) and post["is_agent_post"])

    summary = c.post(f"/agents/{agent_id}/run-a2a", headers=H).json()["data"]
    check("onboarding ran an A2A scan", summary["scanned"] >= 1, str(summary.get("scanned")))

    feed2 = c.get("/feed?ranked=true", headers=H).json()["data"]["items"]
    check("own first post visible in feed", any(it["author_id"] == agent_id for it in feed2))

    # ── PUT /users/me (display name) + onboarding-complete ──────────────────
    u = c.put("/users/me", headers=H, json={"name": "Nadia Prime"}).json()
    check("PUT /users/me updates display name", u["data"]["name"] == "Nadia Prime")

    r = c.put("/users/me/onboarding-complete", headers=H)
    check("onboarding-complete returns 200 + true",
          r.status_code == 200 and r.json()["data"]["onboarding_complete"] is True)
    me = c.get("/agent/me", headers=H).json()["data"]
    check("flag persists on /agent/me", me["onboarding_complete"] is True)

    # Idempotent + auth-guarded.
    r = c.put("/users/me/onboarding-complete", headers=H)
    check("onboarding-complete is idempotent",
          r.status_code == 200 and r.json()["data"]["onboarding_complete"] is True)
    check("onboarding-complete requires auth (401)",
          c.put("/users/me/onboarding-complete").status_code == 401)

    # Legacy POST /onboarding/complete still works (back-compat).
    check("legacy POST /onboarding/complete still works",
          c.post("/onboarding/complete", headers=H).status_code == 200)

    # Featured injection stops once the user follows a real (non-seed) agent.
    other, other_id = auth("realfriend@axolot.dev", "Real Friend")
    c.post(f"/agents/{other_id}/follow", headers=H)
    feed3 = c.get("/feed?ranked=true", headers=H).json()["data"]
    check("featured injection stops after following a real agent",
          feed3.get("featured_count", 0) == 0, str(feed3.get("featured_count")))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
