"""End-to-end test of the Gmail/Calendar tool-use layer. Run: python tool_use_test.py

Verifies the chat agent autonomously invokes the right tool from a plain-English
message and folds real (stub) inbox/calendar data into its reply.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./axolot_tooltest.db")
os.environ.setdefault("USE_STUBS", "true")

if os.path.exists("axolot_tooltest.db"):
    os.remove("axolot_tooltest.db")

from fastapi.testclient import TestClient
from app.main import app
from app.services.agent_tools import build_agent_tools
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

    # tool registry is built and bound
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tools@axolot.dev").first()
        tools = build_agent_tools(db, user)
        names = {t.__name__ for t in tools}
    finally:
        db.close()
    check("all 7 tools registered (gmail + calendar)", len(tools) == 7)
    check(
        "gmail + calendar tools present by name",
        {"list_emails", "read_email", "send_email", "search_emails",
         "list_events", "create_event", "check_availability"} == names,
    )

    # chat: "check my inbox" -> agent calls list_emails -> real stub mail back
    r = c.post("/chat/message", headers=H, json={"message": "Can you check my inbox?"})
    reply = r.json()["data"]["reply"]["content"]
    check("inbox question routes to email tool", "Series A timeline" in reply)

    # chat: schedule question -> agent calls list_events
    r = c.post("/chat/message", headers=H,
               json={"message": "What's on my calendar this week?"})
    reply = r.json()["data"]["reply"]["content"]
    check("schedule question routes to calendar tool",
          "Standup" in reply or "Investor call" in reply)

    # chat: availability question -> check_availability tool
    r = c.post("/chat/message", headers=H,
               json={"message": "Am I free on 2026-06-01?"})
    reply = r.json()["data"]["reply"]["content"]
    check("availability question routes to availability tool",
          "Free slots" in reply or "No free slots" in reply)

    # chat: search -> search_emails tool
    r = c.post("/chat/message", headers=H,
               json={"message": "Search my email for the contract"})
    reply = r.json()["data"]["reply"]["content"]
    check("search question routes to search tool",
          "Contract" in reply or "found in your mail" in reply)

    # non-tool message still answers conversationally (no crash)
    r = c.post("/chat/message", headers=H, json={"message": "hello there"})
    check("plain message still returns a reply", r.status_code == 200
          and bool(r.json()["data"]["reply"]["content"]))

print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
raise SystemExit(0 if ok else 1)
