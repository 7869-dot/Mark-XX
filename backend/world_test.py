"""End-to-end test for Sprint 6 — web access, world posts, trust, collaboration,
privacy. Run: .venv/Scripts/python.exe world_test.py
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_world.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")
os.environ.setdefault("POST_CONFIDENCE_THRESHOLD", "0.4")  # stub confidence is 0.5
if os.path.exists("axolot_world.db"):
    os.remove("axolot_world.db")

from fastapi.testclient import TestClient
from app.main import app
from app.services import privacy_filter

c = TestClient(app)
ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra and not cond else ""))
    ok = ok and bool(cond)


def auth(email, name):
    d = c.post("/auth/google", json={"email": email, "name": name}).json()
    return {"Authorization": f"Bearer {d['data']['access_token']}"}


def aid(h):
    return c.get("/agent/me", headers=h).json()["data"]["id"]


with c:
    # ── privacy_filter unit: PII is structurally stripped ───────────────────
    dirty = "Reach me at jane@acme.com or +1 415 555 1234 — I'm Jane Doe (@jane_d)."
    clean = privacy_filter.strip_pii(dirty, names=["Jane Doe"])
    check("strip_pii removes email", "jane@acme.com" not in clean, clean)
    check("strip_pii removes phone", "555 1234" not in clean and "5551234" not in clean, clean)
    check("strip_pii removes @handle", "@jane_d" not in clean, clean)
    check("strip_pii removes name", "Jane Doe" not in clean, clean)

    A = auth("ada@axolot.dev", "Ada")
    B = auth("bram@axolot.dev", "Bram")
    for h, g in [(A, ["Build an AI startup"]), (B, ["Find a cofounder"])]:
        c.put("/agent/me", headers=h, json={"goals": g, "core_interests": ["ai", "startups"],
              "onboarded": {"completed": True, "step": 4}})
    a_id, b_id = aid(A), aid(B)

    # ── Topic interest profile ──────────────────────────────────────────────
    c.post("/web/topics", headers=A, json={"topic": "AI"})
    c.post("/web/topics", headers=A, json={"topic": "elections"})  # -> geopolitics
    topics = c.get("/web/topics", headers=A).json()["data"]["items"]
    check("topics stored with category", any(t["topic"] == "AI" and t["category"] == "tech" for t in topics), str(topics))
    pulse = c.get("/web/pulse", headers=A).json()["data"]["items"]
    check("world pulse returns tracked topics", len(pulse) >= 2)

    # ── Web search (stub) ───────────────────────────────────────────────────
    sr = c.post("/web/search", headers=A, json={"query": "ai agents"}).json()["data"]
    check("web search returns sourced results", len(sr["results"]) >= 1 and bool(sr["results"][0]["url"]))

    # ── World post engine + trust ───────────────────────────────────────────
    draft = c.post(f"/agents/{a_id}/draft-world-post", headers=A).json()["data"]
    check("draft has confidence + sources", draft["confidence"] > 0 and len(draft["sources"]) >= 1, str(draft.get("confidence")))
    check("MANUAL trust => held pending (not published)", draft["published"] is False and draft["status"] == "pending")
    pend = c.get("/web/pending", headers=A).json()["data"]["items"]
    check("pending queue lists the draft", len(pend) >= 1)
    pid = pend[0]["id"]
    # edit + approve
    c.put(f"/web/pending/{pid}", headers=A, json={"content": "My edited take on AI."})
    appr = c.post(f"/web/pending/{pid}/approve", headers=A).json()["data"]
    check("approve publishes the post", appr["published"] is True and bool(appr["post_id"]))
    feed = c.get("/feed?ranked=false", headers=A).json()["data"]["items"]
    check("published world post appears in feed", any(it["content"] == "My edited take on AI." for it in feed))

    # AUTO trust on a normal category auto-publishes (conf 0.5 >= 0.4 threshold).
    c.put("/web/trust", headers=A, json={"category": "tech", "level": "AUTO"})
    d2 = c.post(f"/agents/{a_id}/draft-world-post", headers=A).json()["data"]
    check("AUTO trust auto-publishes", d2["published"] is True, str(d2))

    # Sensitive category never auto-publishes, even at AUTO.
    c.put("/web/trust", headers=A, json={"category": "geopolitics", "level": "AUTO"})
    d3 = c.post(f"/agents/{a_id}/draft-world-post", headers=A, json={}).json()["data"]
    # draft picks top topic; force geopolitics by making it the only fresh one isn't trivial,
    # so assert the rule directly via a geopolitics draft:
    from app.core.db import SessionLocal
    from app.services import post_engine, agent_web
    db = SessionLocal()
    try:
        from app.models import Agent
        ag = db.query(Agent).filter(Agent.id == a_id).first()
        res = post_engine.draft_world_post(db, ag, topic="the election results")
        check("sensitive topic never auto-publishes at AUTO", res and res["published"] is False and res["category"] == "geopolitics", str(res and {"p": res["published"], "c": res["category"]}))
    finally:
        db.close()

    # ── Collaboration (mutual follow) ───────────────────────────────────────
    c.post(f"/agents/{b_id}/follow", headers=A)
    c.post(f"/agents/{a_id}/follow", headers=B)
    runres = c.post("/collab/run", headers=A).json()["data"]
    check("collab run creates proposals", runres["proposals_created"] >= 2, str(runres))
    prA = c.get("/collab/proposals", headers=A).json()["data"]["items"]
    prB = c.get("/collab/proposals", headers=B).json()["data"]["items"]
    check("both users get a collaboration proposal", len(prA) >= 1 and len(prB) >= 1)
    intent = prA[0]["from_intent"]
    check("proposal intent is anonymized (no other-user name)", "Bram" not in intent and intent.strip() != "", intent)

    # Privacy audit shows the cross-user action with a reason.
    audit = c.get("/web/audit", headers=A).json()["data"]["items"]
    check("privacy audit logs the intent exchange", any(x["action"] == "a2a_intent_signal" and x["reason"] for x in audit), str(audit[:1]))

    # Accept a proposal.
    acc = c.post(f"/collab/proposals/{prA[0]['id']}/accept", headers=A).json()["data"]
    check("accept proposal works", acc["status"] == "accepted")
    check("accepted proposal leaves the pending inbox",
          all(p["id"] != prA[0]["id"] for p in c.get("/collab/proposals", headers=A).json()["data"]["items"]))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
