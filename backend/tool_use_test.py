"""End-to-end test of the Gmail/Calendar tool-use layer. Run: python tool_use_test.py

Verifies the agent autonomously invokes the right tool from a plain-English
message and folds real (stub) inbox/calendar data into its reply.

Post-overhaul note: the legacy /chat/message endpoint that wrapped tool-use was
removed with the social surface. The tool layer itself is unchanged — it lives
in services.gemini.generate_with_tools (+ agent_tools.stub_tool_response for the
offline keyword router), which is the surface this test now exercises directly.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_tooltest.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_tooltest.db"):
    os.remove("axolot_tooltest.db")

from fastapi.testclient import TestClient
from app.main import app
from app.services.agent_tools import build_agent_tools
from app.services.gemini import generate_with_tools
from app.core.db import SessionLocal
from app.models import User

c = TestClient(app)
ok = True


def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond


with c:
    # register
    r = c.post("/auth/google", json={"email": "tools@axolot.dev", "name": "Tool Tester"})
    d = r.json()
    token = d["data"]["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    # tool registry is built and bound. Keep the session open for the duration of
    # the tool calls — the stub tools read inbox/calendar data through this db.
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tools@axolot.dev").first()
        tools = build_agent_tools(db, user)
        names = {t.__name__ for t in tools}

        check("all 7 tools registered (gmail + calendar)", len(tools) == 7)
        check(
            "gmail + calendar tools present by name",
            {"list_emails", "read_email", "send_email", "search_emails",
             "list_events", "create_event", "check_availability"} == names,
        )

        # "check my inbox" -> agent calls list_emails -> real stub mail back
        reply = generate_with_tools("Can you check my inbox?", tools)
        check("inbox question routes to email tool", "Series A timeline" in reply)

        # schedule question -> agent calls list_events
        reply = generate_with_tools("What's on my calendar this week?", tools)
        check("schedule question routes to calendar tool",
              "Standup" in reply or "Investor call" in reply)

        # availability question -> check_availability tool
        reply = generate_with_tools("Am I free on 2026-06-01?", tools)
        check("availability question routes to availability tool",
              "Free slots" in reply or "No free slots" in reply)

        # search -> search_emails tool
        reply = generate_with_tools("Search my email for the contract", tools)
        check("search question routes to search tool",
              "Contract" in reply or "found in your mail" in reply)

        # non-tool message still answers conversationally (no crash, real reply)
        reply = generate_with_tools("hello there", tools)
        check("plain message still returns a reply", bool(reply))
    finally:
        db.close()

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
