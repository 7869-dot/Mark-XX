# Axolotl — The Next Frontier of AI Agents

A multi-agent orchestration platform. A central **Orchestrator** (Axolotl) understands your natural-language request and delegates to specialised sub-agents — currently **Web Agent** (live search & browsing) and **Email Agent** (drafts emails for your approval before sending).

## Architecture

```
User message
    │
    ▼
Orchestrator (claude-sonnet-4-6)
    │  delegate_to_web_agent()
    ├──────────────────────────► Web Agent
    │                            ├─ search_web()  (Tavily)
    │                            └─ fetch_page()  (httpx + BS4)
    │  delegate_to_email_agent()
    └──────────────────────────► Email Agent
                                 └─ draft_email() → user approval → SMTP send
```

Each agent runs its own Claude reasoning loop. The orchestrator streams progress events to the frontend via SSE so you see which agent is active in real time.

---

## Quick start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

### 1. API keys

**Anthropic API key** — <https://console.anthropic.com>

**Tavily API key** (free tier available) — <https://app.tavily.com>

**Gmail App Password** (for the Email Agent):
1. Enable 2-Step Verification on your Google account.
2. Go to <https://myaccount.google.com/apppasswords>.
3. Create an app password — name it "Axolotl".
4. Copy the 16-character password (spaces don't matter).

### 2. Backend

```bash
cd backend
cp .env.example .env
# Fill in your keys in .env
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Open <http://localhost:5173> in your browser.

---

## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
EMAIL_ADDRESS=you@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

---

## Adding a third agent

1. Create `backend/agents/my_agent.py` with a `run(task, on_step=None) -> str` function.
2. Add a tool entry to the `_TOOLS` list in `backend/orchestrator.py`.
3. Handle the new tool name in `orchestrator._dispatch_tool()`.
4. The frontend sidebar picks up the new agent automatically if you add its colour/label to `AGENT_META` in `AgentActivity.jsx`.

That's it — no other files need changing.

---

## Example requests

| Prompt | What happens |
|--------|-------------|
| `Find the latest news on quantum computing` | Web Agent searches, returns sourced summary |
| `Email a summary of recent AI breakthroughs to bob@example.com` | Web Agent researches → Email Agent drafts → you approve → sent |
| `What's the current Bitcoin price?` | Web Agent does a live search |
