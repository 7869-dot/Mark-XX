"""End-to-end test for agent personas (Sprint 3).

Run: .venv/Scripts/python.exe persona_test.py

Covers: persona fields persist, public social card exposes them + post_count,
self-bio generation is persona-aware, autonomous posts differ by voice_tone,
and recommendations carry the recommended agent's voice_tone/interest.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_persona.db")
os.environ.setdefault("USE_STUBS", "true")
if os.path.exists("axolot_persona.db"):
    os.remove("axolot_persona.db")

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


def aid(h):
    return c.get("/agent/me", headers=h).json()["data"]["id"]


PERSONAS = {
    "ada": {"name": "Ada", "voice_tone": "analytical", "posting_style": "long threads",
            "response_style": "Socratic", "core_interests": ["ML", "research", "systems"],
            "posting_frequency_bias": 1.4},
    "bram": {"name": "Bram", "voice_tone": "witty", "posting_style": "hot takes",
             "response_style": "contrarian", "core_interests": ["startups", "culture", "design"],
             "posting_frequency_bias": 1.2},
    "cara": {"name": "Cara", "voice_tone": "warm", "posting_style": "questions",
             "response_style": "affirming", "core_interests": ["wellness", "community"],
             "posting_frequency_bias": 0.8},
}

with c:
    H = {}
    A = {}
    for key, p in PERSONAS.items():
        H[key], _ = auth(f"{key}@axolot.dev", p["name"])
        c.put("/agent/me", headers=H[key], json={
            "goals": ["Grow on the network"], "onboarded": {"completed": True, "step": 4},
            **p,
        })
        c.post("/onboarding/complete", headers=H[key])
        A[key] = aid(H[key])

    # 1. Persona fields persist + come back on /agent/me.
    me = c.get("/agent/me", headers=H["ada"]).json()["data"]
    check("voice_tone persists", me["voice_tone"] == "analytical", str(me.get("voice_tone")))
    check("posting_style persists", me["posting_style"] == "long threads")
    check("response_style persists", me["response_style"] == "Socratic")
    check("core_interests persist", me["core_interests"] == ["ML", "research", "systems"], str(me.get("core_interests")))
    check("posting_frequency_bias persists", abs(me["posting_frequency_bias"] - 1.4) < 1e-6)

    # 2. Public social card exposes persona + post_count.
    card = c.get(f"/agents/{A['bram']}/social", headers=H["ada"]).json()["data"]
    check("social card has voice_tone", card["voice_tone"] == "witty", str(card.get("voice_tone")))
    check("social card has core_interests", card["core_interests"] == ["startups", "culture", "design"])
    check("social card has post_count", "post_count" in card and card["post_count"] >= 0)

    # 3. Self-bio generation is persona-aware (distinct tones → distinct bios).
    bio_ada = c.post(f"/agents/{A['ada']}/generate-bio", headers=H["ada"]).json()["data"]["bio"]
    bio_bram = c.post(f"/agents/{A['bram']}/generate-bio", headers=H["bram"]).json()["data"]["bio"]
    check("Ada bio generated", bool(bio_ada.strip()))
    check("Bram bio generated", bool(bio_bram.strip()))
    check("Ada and Bram bios differ in tone", bio_ada != bio_bram, "bios identical")
    # Stored on the agent + visible on the public card.
    card_ada = c.get(f"/agents/{A['ada']}/social", headers=H["bram"]).json()["data"]
    check("generated bio is stored + public", card_ada["bio"] == bio_ada)

    # 4. Autonomous posts differ by voice_tone (analytical vs witty).
    post_ada = c.post(f"/agents/{A['ada']}/autopost", headers=H["ada"]).json()["data"]["content"]
    post_bram = c.post(f"/agents/{A['bram']}/autopost", headers=H["bram"]).json()["data"]["content"]
    post_cara = c.post(f"/agents/{A['cara']}/autopost", headers=H["cara"]).json()["data"]["content"]
    check("Ada and Bram posts are noticeably different", post_ada != post_bram,
          f"ada={post_ada[:40]!r} bram={post_bram[:40]!r}")
    check("all three personas produce distinct posts",
          len({post_ada, post_bram, post_cara}) == 3)

    # 5. Recommendations carry the recommended agent's persona preview.
    c.post(f"/agents/{A['ada']}/run-a2a", headers=H["ada"])
    recs = c.get(f"/agents/{A['ada']}/recommendations", headers=H["ada"]).json()["data"]["items"]
    check("recommendations returned", len(recs) >= 1, str(len(recs)))
    check("recommendation carries recommended_voice_tone key",
          all("recommended_voice_tone" in r for r in recs))
    check("at least one recommendation previews a voice_tone",
          any(r.get("recommended_voice_tone") for r in recs),
          str([r.get("recommended_voice_tone") for r in recs]))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
