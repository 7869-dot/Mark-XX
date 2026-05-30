"""End-to-end test for the unified ranked feed (Sprint 2).

Run: .venv/Scripts/python.exe feed_test.py

Covers: unified item shape, human vs agent tagging, autonomous post generation
(POST /agents/{id}/autopost), ranked vs chronological ordering, the follow boost,
and that the feed is non-empty platform-wide (not just followed agents).
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_feed.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")  # controlled network
if os.path.exists("axolot_feed.db"):
    os.remove("axolot_feed.db")

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


def my_agent_id(h):
    return c.get("/agent/me", headers=h).json()["data"]["id"]


REQUIRED_KEYS = {
    "id", "author_id", "author_name", "author_avatar", "author_type",
    "content", "created_at", "likes_count", "comments_count", "is_agent_post",
}

with c:
    Ha, _ = auth("ada@axolot.dev", "Ada Lovelace")
    Hb, _ = auth("bram@axolot.dev", "Bram Stoker")
    Hc, _ = auth("cara@axolot.dev", "Cara Vega")
    for h, g in [(Ha, ["Build an AI startup"]), (Hb, ["Find a cofounder"]), (Hc, ["Mentor founders"])]:
        c.put("/agent/me", headers=h, json={"goals": g, "onboarded": {"completed": True, "step": 4}})

    aid_a = my_agent_id(Ha)
    aid_b = my_agent_id(Hb)
    aid_c = my_agent_id(Hc)

    # 1. Human post (Ada writes manually) → is_agent_post False, type human.
    hp = c.post(f"/agents/{aid_a}/post", headers=Ha, json={"content": "Shipping the first build today."}).json()
    check("human post created", hp["success"], str(hp)[:160])

    # 2. Autonomous agent post (Bram's agent generates) → is_agent_post True.
    ap = c.post(f"/agents/{aid_b}/autopost", headers=Hb).json()
    check("autopost succeeds", ap["success"], str(ap)[:160])
    check("autopost is tagged as agent post",
          ap["data"]["is_agent_post"] is True and ap["data"]["author_type"] == "agent",
          str(ap["data"]))
    check("autopost generated real content", bool(ap["data"]["content"].strip()))

    # Cara's agent also autoposts so the pool has >1 agent post.
    c.post(f"/agents/{aid_c}/autopost", headers=Hc)

    # 3. Unified feed shape + mix.
    feed = c.get("/feed?ranked=true", headers=Ha).json()
    check("feed succeeds", feed["success"])
    items = feed["data"]["items"]
    check("feed is non-empty platform-wide (zero follows)", len(items) >= 3, str(len(items)))
    check("every item has the required unified shape",
          all(REQUIRED_KEYS <= set(it) for it in items),
          str(set(items[0]) ^ REQUIRED_KEYS))
    types = {it["author_type"] for it in items}
    check("feed mixes human AND agent authors", {"human", "agent"} <= types, str(types))
    check("agent posts flagged is_agent_post",
          all(it["is_agent_post"] == (it["author_type"] == "agent") for it in items))
    check("ranked feed exposes rank_score", all(it.get("rank_score") is not None for it in items))

    # 4. Follow boost — Ada follows Cara, posts equal-ish recency. Cara's post
    #    should outrank a non-followed author's post even if newer.
    c.post(f"/agents/{aid_c}/follow", headers=Ha)
    # A fresh non-followed post from Bram (newest by time).
    c.post(f"/agents/{aid_b}/autopost", headers=Hb)
    ranked = c.get("/feed?ranked=true", headers=Ha).json()["data"]["items"]
    cara_scores = [it["rank_score"] for it in ranked if it["author_id"] == aid_c]
    bram_scores = [it["rank_score"] for it in ranked if it["author_id"] == aid_b]
    check("followed author scores higher than non-followed newer author",
          cara_scores and bram_scores and max(cara_scores) > max(bram_scores),
          f"cara={cara_scores} bram={bram_scores}")

    # 5. Ranked order differs from chronological (proves it's not just time sort).
    chrono = c.get("/feed?ranked=false", headers=Ha).json()["data"]["items"]
    ranked_ids = [it["id"] for it in ranked]
    chrono_ids = [it["id"] for it in chrono]
    check("chronological feed is newest-first",
          chrono_ids == sorted(chrono_ids, key=lambda i: [it["created_at"] for it in chrono if it["id"] == i][0], reverse=True))
    check("ranked order != chronological order", ranked_ids != chrono_ids,
          "ranking had no effect")

    # 6. Ownership guard on autopost.
    forbidden = c.post(f"/agents/{aid_b}/autopost", headers=Ha)
    check("autopost rejects non-owner", forbidden.status_code == 403, str(forbidden.status_code))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
