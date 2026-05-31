"""Smoke test for the Axolot MCP server + client.

Drives the AxolotClient (what the MCP tools call) against the real FastAPI app
via the TestClient transport — no network, real DB. Run:
    .venv/Scripts/python.exe mcp_smoke_test.py
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_mcp.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")
os.environ.setdefault("POST_CONFIDENCE_THRESHOLD", "0.4")
if os.path.exists("axolot_mcp.db"):
    os.remove("axolot_mcp.db")

# Make the repo root importable so `axolot_mcp` resolves from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from axolot_mcp import AxolotClient
import axolot_mcp.server as server

ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra and not cond else ""))
    ok = ok and bool(cond)


with TestClient(app) as c:  # runs lifespan -> create_all
    # Mint a JWT the way the web app does.
    d = c.post("/auth/google", json={"email": "mcp@axolot.dev", "name": "MCP User"}).json()
    token = d["data"]["access_token"]
    c.put("/agent/me", headers={"Authorization": f"Bearer {token}"},
          json={"name": "Axo", "goals": ["Build an AI startup"], "core_interests": ["ai"],
                "onboarded": {"completed": True, "step": 4}})
    # A second user to collaborate with.
    c.post("/auth/google", json={"email": "peer@axolot.dev", "name": "Peer Person"})

    # AxolotClient driven through the TestClient transport (real API, no network).
    client = AxolotClient(base_url="http://testserver", token=token, http=c)

    ident = client.validate()
    check("validate() loads agent context", bool(ident["agent_id"]) and ident["agent_name"] == "Axo", str(ident))

    # Bad token -> auth error.
    try:
        AxolotClient(base_url="http://testserver", token="bogus", http=c).validate()
        check("invalid token rejected", False)
    except Exception:
        check("invalid token rejected", True)

    # agent_memory_update -> topic profile.
    mem = client.memory_update("topic", "ai agents")
    check("agent_memory_update adds a topic", mem["applied"] == "topic", str(mem))

    # agent_search -> sourced results.
    sr = client.search("ai agents")
    check("agent_search returns sourced results", len(sr["results"]) >= 1 and bool(sr["results"][0]["url"]))

    # agent_post (AUTO) -> published.
    posted = client.post("ai agents", trust_level="AUTO")
    check("agent_post(AUTO) publishes", posted.get("published") is True, str(posted))

    # agent_post with explicit content -> direct post.
    direct = client.post("ai", content="My direct take, posted via MCP.")
    check("agent_post(content) posts directly", direct.get("published") is True and direct.get("mode") == "direct")

    # agent_status.
    st = client.status()
    check("agent_status reports tracking + trust", "ai agents" in st["tracking"] and isinstance(st["trust"], dict), str(st)[:160])

    # agent_collaborate -> PII-stripped proposal to peer.
    collab = client.collaborate("peer@axolot.dev", "find a backend co-founder, email me at me@x.com")
    check("agent_collaborate succeeds", collab.get("ok") is True, str(collab))
    check("agent_collaborate strips PII from intent", "me@x.com" not in collab.get("intent", ""), str(collab.get("intent")))

    # agent_feed.
    feed = client.feed(10)
    check("agent_feed returns activity", len(feed["items"]) >= 1)

    # Resources.
    prof = client.profile()
    check("resource profile() has identity + topics", prof["name"] == "Axo" and "ai agents" in prof["tracked_topics"])
    pulse = client.pulse()
    check("resource pulse() returns tracked topics", len(pulse["items"]) >= 1)

    # Server module wires the tools/resources.
    for t in ("agent_post", "agent_search", "agent_status", "agent_collaborate", "agent_memory_update", "agent_feed"):
        check(f"server exposes tool {t}", callable(getattr(server, t, None)))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
