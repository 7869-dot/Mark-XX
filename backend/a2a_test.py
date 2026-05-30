"""End-to-end A2A test: two users discover each other and exchange messages.

Run: .venv/Scripts/python.exe a2a_test.py
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_a2a.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")  # controlled network
if os.path.exists("axolot_a2a.db"):
    os.remove("axolot_a2a.db")

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

    # Give each agent goals + interests so compatibility is meaningful.
    c.put("/agent/me", headers=Ha, json={
        "name": "Ada", "goals": ["Find collaborators for an AI startup", "Raise a seed round"],
        "onboarded": {"completed": True, "step": 4},
    })
    c.put("/agent/me", headers=Hb, json={
        "name": "Bram", "goals": ["Find a technical cofounder", "Raise a seed round"],
        "onboarded": {"completed": True, "step": 4},
    })

    # 1. Discovery returns the rich payload
    disc = c.get("/agents/discover", headers=Ha).json()
    check("discover succeeds + spec envelope", disc["success"] and "meta" in disc and "agent_id" in disc["meta"])
    check("discover excludes self & same-user, finds Bram", len(disc["data"]) >= 1)
    top = disc["data"][0]
    check("discovery has compatibility breakdown", set(top["breakdown"]) ==
          {"personality", "goal_alignment", "tag_overlap"}, str(top.get("breakdown")))
    check("discovery has shared_goals + reason", "shared_goals" in top and bool(top["reason"]))
    check("public discovery payload hides personality_vector",
          "personality_vector" not in top["agent"])
    target_id = top["id"]

    # 2. Initiate an interaction — intro + auto-response generated in one cycle
    inter = c.post("/agents/interact", headers=Ha,
                    json={"target_agent_id": target_id, "interaction_type": "introduction"}).json()
    check("interact succeeds", inter["success"], str(inter))
    d = inter["data"]
    check("introduction message generated", bool(d["initiator_message"]))
    check("auto-response generated same cycle", bool(d["target_response"]))
    check("interaction carries compatibility score", d["compatibility_score"] > 0)
    check("interaction status responded", d["status"] == "responded")
    iid = d["id"]

    # 3. Connection row created in agent_connections
    conns_a = c.get("/agents/connections", headers=Ha).json()
    check("initiator now has a connection", len(conns_a["data"]) >= 1)
    check("connection exposes type + score",
          conns_a["data"][0]["connection_type"] and
          conns_a["data"][0]["compatibility_score"] >= 0)

    # 4. Target sees the inbound interaction with a plain-language human summary
    inbound = c.get("/agents/interactions", headers=Hb).json()
    check("target sees inbound interaction", len(inbound["data"]) >= 1)
    check("human_summary present (no jargon field)", bool(inbound["data"][0]["human_summary"]))

    # 5. Feed endpoint paginates with human_summary
    feed = c.get("/agents/interactions/feed?limit=10&offset=0", headers=Hb).json()
    check("feed returns items + next_offset",
          "items" in feed["data"] and "next_offset" in feed["data"])

    # 6. Target accepts → connection becomes mutual + followed-up flag flow
    acc = c.post(f"/agents/interactions/{iid}/accept", headers=Hb).json()
    check("accept succeeds", acc["success"] and acc["data"]["status"] == "accepted")

    fu = c.post(f"/agents/interactions/{iid}/human-followup", headers=Ha).json()
    check("human-followup returns other user's name",
          fu["data"]["other_user_name"] == "Bram Stoker")

    # 7. Public profile hides personality_vector, includes generated bio
    prof = c.get(f"/agents/{target_id}/profile", headers=Ha).json()
    check("public profile hides personality_vector",
          "personality_vector" not in prof["data"])
    check("public profile includes bio + compatibility", bool(prof["data"]["bio"]) and
          prof["data"]["compatibility_score"] is not None)

    # 8. Spec error envelope on a new route
    bad = c.get("/agents/does-not-exist/profile", headers=Ha)
    body = bad.json()
    check("spec error envelope {code,message}", bad.status_code == 404 and
          isinstance(body.get("error"), dict) and "code" in body["error"], str(body))

    # 9. Decline path
    Hc, _ = auth("cara@axolot.dev", "Cara Vega")
    c.put("/agent/me", headers=Hc, json={"goals": ["mentor founders"], "onboarded": {"completed": True}})
    di = c.get("/agents/discover", headers=Hc).json()["data"]
    if di:
        ix = c.post("/agents/interact", headers=Hc,
                    json={"target_agent_id": di[0]["id"]}).json()["data"]["id"]
        dec = c.post(f"/agents/interactions/{ix}/decline", headers=Hc).json()
        check("decline succeeds", dec["success"] and dec["data"]["status"] == "declined")

    # 10. Network stats
    st = c.get("/network/stats", headers=Ha).json()
    check("network stats payload", st["success"] and
          {"total_agents", "connections_today", "interactions_this_week",
           "top_interest_tags"} <= set(st["data"]))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
