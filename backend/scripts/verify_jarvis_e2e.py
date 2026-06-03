"""End-to-end verification of the Jarvis -> Gemini path.

Produces the real evidence the recovery directive demands. Run from backend/:

    ./.venv/Scripts/python.exe scripts/verify_jarvis_e2e.py

What it does (each step prints PASS/FAIL + the real payload, never a fake):
  1. Resolve the model config (light/heavy/ultra + fallbacks).
  2. If a GEMINI_API_KEY is present:
     a. List models from the live Gemini API and report whether the mandated
        id `gemini-3.1-flash` is actually offered (the authoritative validity
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

MANDATED_MODEL = "gemini-3.1-flash"


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


def step3_jarvis_endpoint() -> None:
    section("STEP 3 — POST /jarvis/chat through the real FastAPI app")
    from fastapi.testclient import TestClient
    from app.core.db import SessionLocal
    from app.core.security import create_access_token
    from app.models import User
    import app.main as m

    body = {"message": "hello", "mode": "default"}
    # Enter the app lifespan first: startup runs Base.metadata.create_all +
    # run_schema_sync, which self-heals any column drift on the bound DB before
    # we touch it (same path production uses on boot).
    with TestClient(m.app) as client:
        # Real user row + real JWT (same code path production uses).
        db = SessionLocal()
        user = User(id=str(uuid.uuid4()), email=f"verify+{uuid.uuid4().hex[:8]}@axolot.local", name="E2E Verify")
        db.add(user)
        db.commit()
        token = create_access_token(user.id)
        db.close()

        print("POST /jarvis/chat")
        print("REQUEST :", json.dumps(body))
        r = client.post("/jarvis/chat", json=body, headers={"Authorization": f"Bearer {token}"})
    print("STATUS  :", r.status_code)
    payload = r.json()
    print("RESPONSE:", json.dumps(payload, indent=2)[:1200])
    ok = r.status_code == 200 and payload.get("success") is True and payload.get("data", {}).get("reply")
    print(f"\n[{'PASS' if ok else 'FAIL'}] endpoint returned 200 + valid envelope with a reply")
    if not ok:
        raise SystemExit(3)
    # Honesty: with no key the reply is the deterministic stub, not a real model
    # call. The directive forbids a stubbed Jarvis answer in production — so flag
    # exactly which path produced this reply.
    from app.core.config import settings
    if settings.USE_STUBS or not (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")):
        print("[NOTE] reply was produced by the offline STUB (no GEMINI_API_KEY) — "
              "plumbing is proven, but this is NOT a real Gemini response.")


if __name__ == "__main__":
    step1_config()
    live_ok = step2_live_gemini()
    step3_jarvis_endpoint()
    section("SUMMARY")
    print("Step 1 (config single-model, no fallback): PASS")
    print("Step 2 (live Gemini model+generation)    :", "PASS" if live_ok else "BLOCKED (no key)")
    print("Step 3 (/jarvis/chat real endpoint)      : PASS")
    if not live_ok:
        print("\nNOT COMPLETE: a real Gemini response has NOT been produced because no")
        print("GEMINI_API_KEY is available. Supply one and re-run to finish verification.")
        sys.exit(1)
