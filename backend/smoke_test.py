"""End-to-end smoke test of the agent lifecycle. Run: python smoke_test.py"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_smoke.db")
os.environ.setdefault("USE_STUBS", "true")

# fresh db
if os.path.exists("axolot_smoke.db"):
    os.remove("axolot_smoke.db")

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    # 1. register -> agent auto-created
    r = c.post("/auth/google", json={"email": "smoke@axolot.dev", "name": "Smoke Test"})
    d = r.json()
    check("register returns envelope", d["success"] and "data" in d and "meta" in d)
    token = d["data"]["access_token"]
    refresh = d["data"]["refresh_token"]
    H = {"Authorization": f"Bearer {token}"}

    me = c.get("/agent/me", headers=H).json()
    check("agent auto-created with default personality",
          me["success"] and me["data"]["personality_vector"]["openness"] == 0.5)

    # 2. onboarding update
    up = c.put("/agent/me", headers=H, json={
        "name": "Vera", "goals": ["Find collaborators in fintech"],
        "personality_vector": {"openness": 0.7, "directness": 0.8, "ambition": 0.9,
                               "sociability": 0.7, "risk_tolerance": 0.6},
        "onboarded": {"completed": True, "step": 4},
    }).json()
    check("agent update persists name", up["data"]["name"] == "Vera")

    # 3. create task -> runs via stub -> completes
    t = c.post("/tasks/create", headers=H, json={
        "title": "Research fintech fundraising", "description": "Find timelines",
        "task_type": "research", "priority": 4, "requires_human_approval": False,
    }).json()
    check("task created", t["success"])
    tid = t["data"]["id"]
    got = c.get(f"/tasks/{tid}", headers=H).json()
    # The engine ran if it produced a result and reached a terminal/awaiting state.
    # (The agent may legitimately escalate a no-approval task to awaiting_human.)
    check("task engine ran (not stuck in running/queued)",
          got["data"]["status"] in ("completed", "awaiting_human"))
    check("task has structured result", bool(got["data"]["result"]))

    # 4. approval flow
    t2 = c.post("/tasks/create", headers=H, json={
        "title": "Send outbound", "description": "Draft+send",
        "task_type": "outreach", "priority": 3, "requires_human_approval": True,
    }).json()
    tid2 = t2["data"]["id"]
    pend = c.get("/tasks/pending", headers=H).json()
    check("task awaiting approval surfaces in pending",
          any(x["id"] == tid2 for x in pend["data"]))
    ap = c.post(f"/tasks/{tid2}/approve", headers=H).json()
    check("approve transitions to completed", ap["data"]["status"] == "completed")

    # 5. reputation is event-sourced and moved off baseline
    stats = c.get("/agent/stats", headers=H).json()
    check("reputation changed via events", stats["data"]["reputation_score"] != 50.0)
    check("time_saved_minutes_week present", "time_saved_minutes_week" in stats["data"])

    # 6. A2A — seed a second user and interact
    c.post("/auth/google", json={"email": "layla@axolot.dev", "name": "Layla H"})
    disc = c.get("/agents/discover", headers=H).json()
    check("discovery returns compatible agents", len(disc["data"]) >= 1)
    target = disc["data"][0]["id"]
    inter = c.post("/agents/interact", headers=H, json={"target_agent_id": target}).json()
    check("A2A interaction auto-responds in same cycle",
          inter["success"] and bool(inter["data"]["response"]))

    # 7. A2A rate limit (3/day) enforced at API layer
    for _ in range(3):
        c.post("/agents/interact", headers=H, json={"target_agent_id": target})
    limited = c.post("/agents/interact", headers=H, json={"target_agent_id": target})
    check("A2A daily limit enforced (429)", limited.status_code == 429)

    # 8. refresh rotation: old token cannot be reused
    rr = c.post("/auth/refresh", json={"refresh_token": refresh}).json()
    check("refresh issues new pair", rr["success"])
    reuse = c.post("/auth/refresh", json={"refresh_token": refresh})
    check("reused refresh token rejected", reuse.status_code == 401)

    # 9. health + platform + public profile with bio
    h = c.get("/health").json()
    check("health reports checks", "checks" in h["data"])
    prof = c.get(f"/agents/{target}/profile", headers=H).json()
    check("public profile has generated bio", "bio" in prof["data"])

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
