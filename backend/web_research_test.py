"""Web-agent search/scrape + orchestration-loop test (hermetic, no browser).

Exercises the token-interception loop, HTML cleaning, the stub-aware search
path, and the /agents/web/research endpoint — all under USE_STUBS so it needs no
network and no Playwright/Chromium install. Run: python web_research_test.py
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_webres.db")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("SEED_PERSONAS_ON_STARTUP", "false")
if os.path.exists("axolot_webres.db"):
    os.remove("axolot_webres.db")

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.services import web_research, agent_web
from app.services.local_browser import clean_html, _decode_ddg_href

c = TestClient(app)
ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra and not cond else ""))
    ok = ok and bool(cond)


# ── 1. HTML cleaning strips scripts/CSS/nav and extracts body text ───────────
HTML = """
<html><head><title>Test Page</title><style>.x{color:red}</style></head>
<body>
  <nav>Home About Contact</nav>
  <script>console.log('tracking')</script>
  <main><h1>Real Heading</h1><p>The meaningful body content lives here.</p></main>
  <footer>copyright</footer>
</body></html>
"""
cleaned = clean_html(HTML, "https://example.com")
check("clean_html extracts title", cleaned["title"] == "Test Page")
check("clean_html keeps body text", "meaningful body content" in cleaned["text"])
check("clean_html strips <script>", "tracking" not in cleaned["text"])
check("clean_html strips <style>", "color:red" not in cleaned["text"])
check("clean_html strips <nav>", "About Contact" not in cleaned["text"])

# ── 2. DuckDuckGo redirect-link decoding ─────────────────────────────────────
decoded = _decode_ddg_href("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x")
check("ddg href decodes to real url", decoded == "https://example.com/a", decoded)

# ── 3. Stub-aware search is hermetic + shaped ────────────────────────────────
results = agent_web.web_search("vector databases", max_results=3)
check("web_search returns results", len(results) == 3, str(len(results)))
check("results have title+url+snippet", all(k in results[0] for k in ("title", "url", "snippet")))

# ── 4. Orchestration loop intercepts SEARCH then VISIT then synthesises ──────
db = SessionLocal()
script = [
    "[SEARCH: best open-source vector databases 2026]",
    "[VISIT: https://example.com/vector-db-guide]",
    "FINAL ANSWER: pgvector and Qdrant lead for local setups. (https://example.com/vector-db-guide)",
]
seq = {"i": 0}
def scripted(prompt):
    out = script[min(seq["i"], len(script) - 1)]
    seq["i"] += 1
    return out
res = web_research.run_agent_loop(db, None, "find vector dbs", max_steps=4, generate_fn=scripted)
actions = [s["action"] for s in res["steps"]]
check("loop ran SEARCH then VISIT", actions == ["SEARCH", "VISIT"], str(actions))
check("loop captured sources", len(res["sources"]) >= 1, str(res["sources"]))
check("loop returns a final answer with no token", "[SEARCH" not in res["answer"] and bool(res["answer"]))
check("loop reports used_web", res["used_web"] is True)

# A reply with no token on turn 1 ends immediately as the final answer.
res2 = web_research.run_agent_loop(db, None, "say hi", max_steps=3, generate_fn=lambda p: "Just a direct answer.")
check("no-token reply ends loop immediately", res2["used_web"] is False and res2["answer"] == "Just a direct answer.")
db.close()

# ── 5. Endpoint wiring (with c: runs lifespan -> create_all) ─────────────────
with c:
    d = c.post("/auth/google", json={"email": "webres@axolot.dev", "name": "Web Researcher"}).json()
    H = {"Authorization": f"Bearer {d['data']['access_token']}"}
    r = c.post("/agents/web/research", headers=H, json={"query": "open-source LLM serving", "max_steps": 2}).json()
    check("research endpoint returns envelope", r["success"])
    check("research endpoint returns answer + sources keys",
          all(k in r["data"] for k in ("answer", "sources", "steps", "used_web")))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
