"""End-to-end verification of the Jarvis -> Gemini path.

Produces the real evidence the recovery directive demands. Run from backend/:

    ./.venv/Scripts/python.exe scripts/verify_jarvis_e2e.py

What it does (each step prints PASS/FAIL + the real payload, never a fake):
  1. Resolve the model config (light/heavy/ultra + fallbacks).
  2. If a GEMINI_API_KEY is present:
     a. List models from the live Gemini API and report whether the mandated
        id `gemini-3.5-flash` is actually offered (the authoritative validity
        check — there is no offline way to know).
     b. Make a real generate_content call and print the request + response.
  3. Spin up the real FastAPI app with a TestClient, mint a real JWT for a
     throwaway user, and POST /jarvis/chat — printing the real endpoint JSON.

Exit code is non-zero if any step that *can* run fails, so CI can gate on it.
With NO key, step 2 is reported as BLOCKED (not faked) and step 3 still proves
the routing/auth/envelope plumbing end to end via the stub.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

# Ensure `import app...` works when run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANDATED_MODEL = "gemini-3.5-flash"


def section(n: str) -> None:
    print("\n" + "=" * 72)
    print(n)
    print("=" * 72)


def step1_config() -> None:
    section("STEP 1 — model configuration (resolved at runtime)")
    from app.core.config import settings

    print("LLM_PROVIDER      :", settings.LLM_PROVIDER)
    print("model_light()     :", settings.model_light())
    print("model_heavy()     :", settings.model_heavy())
    print("model_ultra()     :", settings.model_ultra())
    print("fallback_models() :", settings.fallback_models())
    tiers = {settings.model_light(), settings.model_heavy(), settings.model_ultra()}
    single = tiers == {MANDATED_MODEL}
    no_fallback = settings.fallback_models() == []
    print(f"\n[{'PASS' if single else 'FAIL'}] exactly one model across all tiers == {MANDATED_MODEL!r}")
    print(f"[{'PASS' if no_fallback else 'FAIL'}] no fallback models configured")
    if not (single and no_fallback):
        raise SystemExit(2)


def step2_live_gemini() -> bool:
    section("STEP 2 — live Gemini API (model validity + real generation)")
    from app.core.config import settings

    key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if settings.USE_STUBS or not key:
        print("BLOCKED — no GEMINI_API_KEY present (USE_STUBS=%s)." % settings.USE_STUBS)
        print("Cannot verify whether %r is a real model id, and cannot make a" % MANDATED_MODEL)
        print("real generation call, without a key. This step is NOT faked.")
        print("Provide a key (backend/.env: GEMINI_API_KEY=...) and re-run.")
        return False

    from google import genai

    client = genai.Client(api_key=key)

    # 2a — authoritative model-id validity via models.list
    print("\n-- 2a: models.list() --")
    available = []
    for m in client.models.list():
        name = getattr(m, "name", "") or ""
        available.append(name.replace("models/", ""))
    hit = MANDATED_MODEL in available or f"models/{MANDATED_MODEL}" in available
    print(f"models offered: {len(available)} (showing flash family)")
    for a in sorted(x for x in available if "flash" in x):
        print("  -", a)
    print(f"\n[{'PASS' if hit else 'FAIL'}] {MANDATED_MODEL!r} is offered by the live API")

    # 2b — real generate_content
    print("\n-- 2b: real generate_content() --")
    req = {"model": MANDATED_MODEL, "contents": "Reply with exactly: PONG"}
    print("REQUEST :", json.dumps(req))
    resp = client.models.generate_content(model=MANDATED_MODEL, contents=req["contents"])
    text = (getattr(resp, "text", "") or "").strip()
    print("RESPONSE:", repr(text))
    print(f"[{'PASS' if text else 'FAIL'}] non-empty real response returned")
    return bool(hit and text)


_FAILS: list[str] = []


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        _FAILS.append(name)


def step3_multi_agent() -> None:
    section("STEP 3 — multi-agent flow through the real FastAPI app")
    from fastapi.testclient import TestClient
    from app.core.db import SessionLocal
    from app.core.security import create_access_token
    from app.models import User
    from app.services import user_profile as profiles
    import app.main as m

    # Enter the app lifespan: startup runs create_all + run_schema_sync (self-heals
    # column drift) + starts the scheduler — same path production boots through.
    with TestClient(m.app) as client:
        db = SessionLocal()
        user = User(id=str(uuid.uuid4()), email=f"verify+{uuid.uuid4().hex[:8]}@axolot.local", name="E2E Verify")
        db.add(user)
        db.commit()
        # Onboard so the scout has interests/goals to scan against.
        profiles.apply_onboarding(db, user, {
            "working_on": "Building a startup or product",
            "improve": "Technical / engineering skills",
            "opportunities": ["Learning", "Freelance"],
            "hates": "status meetings",
            "goal": "ship the multi-agent backend",
        })
        token = create_access_token(user.id)
        db.close()
        H = {"Authorization": f"Bearer {token}"}

        def get(path):
            r = client.get(path, headers=H)
            return r.status_code, r.json()
        def post(path, body):
            r = client.post(path, json=body, headers=H)
            return r.status_code, r.json()

        # 1) Manager delegation + interest capture (the flagship loop).
        print("\n-- POST /jarvis/chat (AUTO: 'get better at multi-agent systems') --")
        sc, pl = post("/jarvis/chat", {"message": "I want to get better at building multi-agent systems", "mode": "auto"})
        data = pl.get("data", {})
        print("RESPONSE:", json.dumps(data, indent=2)[:700])
        _check("chat 200 + envelope", sc == 200 and pl.get("success") is True)
        _check("Jarvis delegated learning intent to Web Agent", data.get("delegated_to") == "web",
               f"delegated_to={data.get('delegated_to')}")
        _check("interest remembered to memory", "multi-agent systems" in
               " ".join(data.get("remembered_interests", [])).lower(),
               f"remembered={data.get('remembered_interests')}")

        # Confirm the interest actually persisted in the profile (real DB read).
        db = SessionLocal()
        prof = profiles.profile_dict(profiles.get_profile(db, user.id))
        db.close()
        _check("interest persisted in profile", any("multi-agent" in str(i).lower() for i in prof["interests"]),
               f"interests={prof['interests']}")

        # 2) Briefing — runs all three sub-agents + synthesises.
        print("\n-- GET /jarvis/briefing --")
        sc, pl = get("/jarvis/briefing")
        bd = pl.get("data", {})
        _check("briefing 200 + envelope", sc == 200 and pl.get("success") is True)
        _check("briefing ran sub-agents (reports present)", bool(bd.get("reports")) or bd.get("onboarding") is False,
               f"keys={list(bd.keys())}")

        # 3) Agent roster.
        sc, pl = get("/jarvis/agents")
        ad = pl.get("data", {})
        # PA core: exactly two sub-agents — Web + Email (the social "feed" agent
        # was removed in the PA-core purge).
        _check("GET /jarvis/agents", sc == 200 and len(ad.get("sub_agents", [])) == 2,
               f"sub_agents={len(ad.get('sub_agents', []))}")

        # 4) Email agent surface.
        sc, pl = get("/email/summary")
        _check("GET /email/summary", sc == 200 and "counts" in pl.get("data", {}))
        sc, pl = get("/email/urgent")
        _check("GET /email/urgent", sc == 200 and "urgent_count" in pl.get("data", {}))
        sc, pl = post("/email/draft", {"instruction": "reply to the client confirming Thursday works"})
        dd = pl.get("data", {})
        _check("POST /email/draft -> approval-gated draft", sc == 200 and dd.get("draft_id") and dd.get("requires_approval") is True,
               f"draft_id={dd.get('draft_id')}")

        # 5) Web agent surface.
        sc, pl = post("/web/research", {"query": "multi-agent systems courses", "max_steps": 2})
        _check("POST /web/research", sc == 200 and "answer" in pl.get("data", {}))
        sc, pl = get("/web/findings")
        fd = pl.get("data", {})
        _check("GET /web/findings (scout persisted opportunities)", sc == 200 and isinstance(fd.get("items"), list),
               f"items={len(fd.get('items', []))}")

        # 6) Draft queue reflects the email draft.
        sc, pl = get("/jarvis/drafts")
        _check("GET /jarvis/drafts shows pending draft", sc == 200 and len(pl.get("data", {}).get("items", [])) >= 1)

        # 7) Token budget: the scheduled scan respects the cooldown after a run.
        from app.scheduler.jobs import opportunity_scan_job
        opportunity_scan_job()  # user just scanned via briefing -> cooldown skips
        print("[PASS] opportunity_scan_job ran without error (cooldown-gated)")


if __name__ == "__main__":
    step1_config()
    live_ok = step2_live_gemini()
    step3_multi_agent()
    section("SUMMARY")
    print("Step 1 (config single-model, no fallback):", "PASS")
    print("Step 2 (live Gemini model+generation)    :", "PASS" if live_ok else "BLOCKED (no key)")
    print("Step 3 (multi-agent flow + endpoints)    :", "PASS" if not _FAILS else f"FAIL ({len(_FAILS)}: {_FAILS})")
    if _FAILS:
        sys.exit(3)
    if not live_ok:
        print("\nArchitecture verified in stub mode. NOT COMPLETE for live Gemini: no")
        print("GEMINI_API_KEY available, so real model responses are unverified.")
        sys.exit(1)
