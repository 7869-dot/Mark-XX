"""End-to-end test for the A2A recommendation pipeline.

Run: .venv/Scripts/python.exe a2a_reco_test.py

Covers: POST /agents/{id}/run-a2a (manual cycle), GET .../recommendations,
mark-seen, and that the cycle records connections/interactions while the
"owner" is entirely offline (no manual /interact call).
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_reco.db")
os.environ.setdefault("USE_STUBS", "true")
if os.path.exists("axolot_reco.db"):
    os.remove("axolot_reco.db")

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
    return {"Authorization": f"Bearer {d['data']['access_token']}"}, d["data"]["user_id"]


with c:
    Ha, _ = auth("ada@axolot.dev", "Ada Lovelace")
    Hb, _ = auth("bram@axolot.dev", "Bram Stoker")
    Hc, _ = auth("cara@axolot.dev", "Cara Vega")

    c.put("/agent/me", headers=Ha, json={
        "name": "Ada", "goals": ["Find collaborators for an AI startup", "Raise a seed round"],
        "onboarded": {"completed": True, "step": 4},
    })
    c.put("/agent/me", headers=Hb, json={
        "name": "Bram", "goals": ["Find a technical cofounder", "Raise a seed round"],
        "onboarded": {"completed": True, "step": 4},
    })
    c.put("/agent/me", headers=Hc, json={
        "name": "Cara", "goals": ["Mentor early founders", "Invest in AI startups"],
        "onboarded": {"completed": True, "step": 4},
    })

    me = c.get("/agent/me", headers=Ha).json()["data"]
    agent_id = me["id"]

    # 1. Manual A2A cycle — the owner is offline; the agent does everything.
    run = c.post(f"/agents/{agent_id}/run-a2a", headers=Ha).json()
    check("run-a2a succeeds + spec envelope", run["success"] and "meta" in run, str(run)[:200])
    summary = run["data"]
    check("cycle scanned other agents", summary["scanned"] >= 2, str(summary.get("scanned")))
    check("cycle produced per-candidate decisions", len(summary["decisions"]) >= 2)
    check("each decision has action + reason",
          all(d["action"] and d["reason"] for d in summary["decisions"]),
          str(summary["decisions"][:1]))
    check("cycle reached out autonomously", len(summary["reached_out"]) >= 1,
          str(summary["reached_out"]))
    check("cycle generated recommendations (<=5)",
          1 <= len(summary["recommendations"]) <= 5, str(len(summary["recommendations"])))
    rec0 = summary["recommendations"][0]
    check("recommendation has user id + reason + score",
          bool(rec0["recommended_user_id"]) and bool(rec0["reason"])
          and rec0["compatibility_score"] >= 0, str(rec0))
    check("recommendation carries a display name", bool(rec0["recommended_name"]))

    # 2. GET recommendations (owner logs back in).
    recs = c.get(f"/agents/{agent_id}/recommendations", headers=Ha).json()
    check("GET recommendations succeeds", recs["success"])
    items = recs["data"]["items"]
    check("unseen recommendations returned", len(items) >= 1)
    check("recommendations are unseen by default", all(not r["seen"] for r in items))

    # 3. Mark one seen.
    rid = items[0]["id"]
    seen = c.post(f"/agents/{agent_id}/recommendations/{rid}/seen", headers=Ha).json()
    check("mark-seen succeeds", seen["success"] and seen["data"]["seen"])
    after = c.get(f"/agents/{agent_id}/recommendations", headers=Ha).json()["data"]["items"]
    check("seen recommendation no longer in unseen list",
          all(r["id"] != rid for r in after))
    with_seen = c.get(
        f"/agents/{agent_id}/recommendations?include_seen=true", headers=Ha
    ).json()["data"]["items"]
    check("include_seen=true returns the seen one too",
          any(r["id"] == rid for r in with_seen))

    # 4. A connection / interaction now exists from the autonomous outreach.
    conns = c.get("/agents/connections", headers=Ha).json()["data"]
    check("autonomous outreach created a connection", len(conns) >= 1, str(len(conns)))

    # 5. Ownership guard — another user can't run my agent's cycle.
    forbidden = c.post(f"/agents/{agent_id}/run-a2a", headers=Hb)
    body = forbidden.json()
    check("run-a2a rejects non-owner",
          forbidden.status_code == 403 and isinstance(body.get("error"), dict),
          str(body))

    # 6. mark all seen
    c.post(f"/agents/{agent_id}/run-a2a", headers=Ha)  # repopulate
    allseen = c.post(f"/agents/{agent_id}/recommendations/seen-all", headers=Ha).json()
    check("seen-all succeeds", allseen["success"])
    remaining = c.get(f"/agents/{agent_id}/recommendations", headers=Ha).json()["data"]["items"]
    check("no unseen recommendations after seen-all", len(remaining) == 0, str(len(remaining)))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
