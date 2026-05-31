"""End-to-end test for Sprint 5 — reactions, notifications, invites, share card.

Run: .venv/Scripts/python.exe engagement_test.py
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_engage.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")  # controlled network
if os.path.exists("axolot_engage.db"):
    os.remove("axolot_engage.db")

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
    return {"Authorization": f"Bearer {d['data']['access_token']}"}


def aid(h):
    return c.get("/agent/me", headers=h).json()["data"]["id"]


def notif_types(h):
    items = c.get("/notifications", headers=h).json()["data"]["items"]
    return [n["type"] for n in items]


with c:
    A = auth("ada@axolot.dev", "Ada")
    B = auth("bram@axolot.dev", "Bram")
    for h, g in [(A, ["Build an AI startup"]), (B, ["Find a cofounder"])]:
        c.put("/agent/me", headers=h, json={"goals": g, "voice_tone": "witty",
              "core_interests": ["ai", "startups"], "onboarded": {"completed": True, "step": 4}})
    a_id, b_id = aid(A), aid(B)

    # Ada's agent autoposts → Ada gets an agent_post notification.
    post = c.post(f"/agents/{a_id}/autopost", headers=A).json()["data"]
    post_id = post["id"]
    check("autopost fires agent_post notification", "agent_post" in notif_types(A), str(notif_types(A)))

    # ── Likes ───────────────────────────────────────────────────────────────
    like = c.post(f"/posts/{post_id}/like", headers=B).json()["data"]
    check("like returns liked=true + count 1", like["liked"] is True and like["likes_count"] == 1, str(like))
    gl = c.get(f"/posts/{post_id}/likes", headers=B).json()["data"]
    check("get likes: viewer_has_liked true", gl["viewer_has_liked"] is True and gl["likes_count"] == 1)
    check("like fires social_reaction to post owner", "social_reaction" in notif_types(A))

    # ── Comments ────────────────────────────────────────────────────────────
    cm = c.post(f"/posts/{post_id}/comments", headers=B, json={"content": "Great take!"}).json()["data"]
    check("comment created with author info", cm["content"] == "Great take!" and bool(cm["author"]["name"]))
    cl = c.get(f"/posts/{post_id}/comments", headers=A).json()["data"]
    check("comments list returns the comment", cl["count"] == 1 and cl["items"][0]["content"] == "Great take!")

    # ── Feed reflects real counts ───────────────────────────────────────────
    feed = c.get("/feed?ranked=false", headers=B).json()["data"]["items"]
    fp = next((it for it in feed if it["id"] == post_id), None)
    check("feed shows real likes_count/comments_count + viewer_has_liked",
          fp and fp["likes_count"] == 1 and fp["comments_count"] == 1 and fp["viewer_has_liked"] is True,
          str(fp and {k: fp[k] for k in ("likes_count", "comments_count", "viewer_has_liked")}))

    # Toggle like off.
    unl = c.post(f"/posts/{post_id}/like", headers=B).json()["data"]
    check("unlike toggles off", unl["liked"] is False and unl["likes_count"] == 0)

    # ── Notifications read endpoints ────────────────────────────────────────
    nlist = c.get("/notifications", headers=A).json()["data"]
    check("notifications list + unseen_count", nlist["unseen_count"] >= 1 and len(nlist["items"]) >= 1)
    first_id = nlist["items"][0]["id"]
    check("mark one seen", c.post(f"/notifications/{first_id}/seen", headers=A).json()["data"]["seen"] is True)
    c.post("/notifications/seen-all", headers=A)
    check("seen-all clears unseen", c.get("/notifications", headers=A).json()["data"]["unseen_count"] == 0)

    # ── run-a2a fires recommendation notifications ──────────────────────────
    c.post(f"/agents/{a_id}/run-a2a", headers=A)
    check("run-a2a fires recommendation notification", "recommendation" in notif_types(A), str(notif_types(A)))

    # ── Invite flow ─────────────────────────────────────────────────────────
    code = c.post("/invites/generate", headers=A).json()["data"]["code"]
    check("invite code is 8 chars", len(code) == 8, code)
    mine = c.get("/invites/mine", headers=A).json()["data"]
    check("invites/mine lists the unused code", any(x["code"] == code and not x["used"] for x in mine["items"]))

    # New user C redeems A's code → welcome DM + both notified.
    C = auth("cara@axolot.dev", "Cara")
    c.put("/agent/me", headers=C, json={"goals": ["mentor"], "onboarded": {"completed": True}})
    red = c.post("/invites/redeem", headers=C, json={"code": code}).json()["data"]
    check("redeem succeeds + returns inviter agent + message", red["ok"] is True and bool(red.get("message")), str(red))
    check("redeemer (new user) gets INVITE notification", "invite" in notif_types(C), str(notif_types(C)))
    check("inviter gets INVITE notification", "invite" in notif_types(A), str(notif_types(A)))
    check("invited_count increments", c.get("/invites/mine", headers=A).json()["data"]["invited_count"] == 1)

    # Single-use enforcement.
    again = c.post("/invites/redeem", headers=B, json={"code": code}).json()["data"]
    check("invite code is single-use", again["ok"] is False and again["reason"] == "already_used", str(again))

    # ── Shareable card works WITHOUT auth ───────────────────────────────────
    card = c.get(f"/agents/{a_id}/card")  # no Authorization header
    check("card endpoint is public (200 no auth)", card.status_code == 200, str(card.status_code))
    cd = card.json()["data"]
    check("card has name/bio/voice_tone/interests/recent_post",
          bool(cd["name"]) and "bio" in cd and "voice_tone" in cd and "interests" in cd and "recent_post" in cd,
          str(list(cd.keys())))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
