"""End-to-end test of the agent social graph. Run: python social_test.py

Covers: follow / unfollow (idempotent), followers / following lists,
follow-ranked discovery, posting, and the followed-only feed.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_social.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_social.db"):
    os.remove("axolot_social.db")

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


def register(email, name):
    d = c.post("/auth/google", json={"email": email, "name": name}).json()
    return {"H": {"Authorization": f"Bearer {d['data']['access_token']}"},
            "agent_id": d["meta"]["agent_id"]}


with c:
    a = register("a@axolot.dev", "Ada")
    b = register("b@axolot.dev", "Boris")
    cc = register("c@axolot.dev", "Cleo")

    # ── Follow ──────────────────────────────────────────────────────────────
    r = c.post(f"/agents/{b['agent_id']}/follow", headers=a["H"]).json()
    check("A follows B", r["success"] and r["data"]["following"] is True
          and r["data"]["follower_count"] == 1)

    # idempotent
    r = c.post(f"/agents/{b['agent_id']}/follow", headers=a["H"]).json()
    check("re-follow is idempotent (still 1)", r["data"]["follower_count"] == 1)

    # cannot follow self
    r = c.post(f"/agents/{a['agent_id']}/follow", headers=a["H"])
    check("cannot follow self (400)", r.status_code == 400)

    # ── Followers / following ───────────────────────────────────────────────
    r = c.get(f"/agents/{b['agent_id']}/followers", headers=b["H"]).json()
    check("B's followers list contains A",
          any(card["id"] == a["agent_id"] for card in r["data"]))

    r = c.get(f"/agents/{a['agent_id']}/following", headers=a["H"]).json()
    check("A's following list contains B",
          any(card["id"] == b["agent_id"] for card in r["data"]))
    check("card exposes follower_count + is_following",
          all(k in r["data"][0] for k in ("follower_count", "is_following", "bio", "avatar_seed")))

    # ── Posts ───────────────────────────────────────────────────────────────
    r = c.post(f"/agents/{b['agent_id']}/post", headers=b["H"],
               json={"content": "Boris agent online — exploring fintech leads."}).json()
    check("B creates a post", r["success"] and r["data"]["agent"]["id"] == b["agent_id"])

    # cannot post as another agent
    r = c.post(f"/agents/{b['agent_id']}/post", headers=a["H"],
               json={"content": "impersonation attempt"})
    check("cannot post as another agent (403)", r.status_code == 403)

    # over-length post rejected by schema
    r = c.post(f"/agents/{a['agent_id']}/post", headers=a["H"],
               json={"content": "x" * 501})
    check("post over 500 chars rejected (422)", r.status_code == 422)

    # ── Feed ────────────────────────────────────────────────────────────────
    r = c.get("/feed", headers=a["H"]).json()
    check("A's feed contains B's post (A follows B)",
          any("fintech leads" in p["content"] for p in r["data"]["items"]))

    c.post(f"/agents/{a['agent_id']}/post", headers=a["H"],
           json={"content": "Ada agent: shipped the social graph."})
    r = c.get("/feed", headers=a["H"]).json()
    check("A's feed includes A's own post",
          any("social graph" in p["content"] for p in r["data"]["items"]))

    c.post(f"/agents/{cc['agent_id']}/post", headers=cc["H"],
           json={"content": "Cleo agent: nobody follows me yet."})
    r = c.get("/feed", headers=a["H"]).json()
    check("A's feed excludes unfollowed C's post",
          not any("nobody follows me" in p["content"] for p in r["data"]["items"]))

    # post history
    r = c.get(f"/agents/{b['agent_id']}/posts", headers=a["H"]).json()
    check("B's post history returns B's post",
          len(r["data"]["items"]) == 1 and "fintech" in r["data"]["items"][0]["content"])

    # single-agent social card (powers the profile page)
    r = c.get(f"/agents/{b['agent_id']}/social", headers=a["H"]).json()
    check("single agent social card returns counts + bio",
          r["success"] and r["data"]["id"] == b["agent_id"]
          and "follower_count" in r["data"] and "bio" in r["data"])

    # ── Discovery ───────────────────────────────────────────────────────────
    r = c.get("/social/discover", headers=cc["H"]).json()
    ids = [card["id"] for card in r["data"]]
    check("discover excludes the requester", cc["agent_id"] not in ids)
    check("discover ranks B (has a follower) above C-equivalent",
          ids and ids[0] == b["agent_id"])

    # ── Unfollow ────────────────────────────────────────────────────────────
    r = c.request("DELETE", f"/agents/{b['agent_id']}/unfollow", headers=a["H"]).json()
    check("A unfollows B", r["data"]["following"] is False
          and r["data"]["follower_count"] == 0)

    r = c.get("/feed", headers=a["H"]).json()
    check("after unfollow, B's post leaves A's feed",
          not any("fintech leads" in p["content"] for p in r["data"]["items"]))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
