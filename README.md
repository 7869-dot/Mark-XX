# Axolotl — Jarvis, your AI Chief of Staff

A multi-agent personal assistant. **Jarvis** (the orchestrator) manages your inbox, calendar, and founder network while you're offline — and surfaces everything for one-click approval before anything is sent or changed.

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  Frontend (React + Framer Motion)                                 │
│  LEFT: Jarvis hub (briefing · chat · nudge feed)                  │
│  RIGHT: Sub-agent panels (Web · Email & Schedule · Connections)   │
│         + "Needs your approval" surface                           │
└────────────────────────────┬──────────────────────────────────────┘
                             │ SSE + REST (JWT)
┌────────────────────────────▼──────────────────────────────────────┐
│  FastAPI backend                                                  │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────────────┐  │
│  │ Jarvis   │  │ Schedule Agent │  │ Connection Agent         │  │
│  │ (chief)  │→ │ Gmail+Calendar │  │ wraps matchmaker pipeline │  │
│  └──────────┘  └────────────────┘  └──────────────────────────┘  │
│  ┌──────────┐  ┌──────────────────────────────────────────────┐  │
│  │ Web Agent│  │ Proactivity engine: briefings + nudges       │  │
│  └──────────┘  └──────────────────────────────────────────────┘  │
│  SQLite (proposed_actions · nudges · connection_proposals · …)    │
└───────────────────────────────────────────────────────────────────┘
```

### Sub-agents

| Agent | Tools | Action gate |
|---|---|---|
| **Web** | `search_web`, `fetch_page` | None — read-only |
| **Email & Schedule** | `list_recent_emails`, `read_email`, `get_today_schedule` | `draft_email_reply`, `propose_calendar_event` → `proposed_actions` table (pending) |
| **Connection** | wraps `matchmaker.run_cycle` | `connection_approval` → `proposed_actions` (pending) |

Everything that touches the outside world (Gmail send, Calendar create, contact exchange) only executes after the user approves via `POST /proposed-actions/{id}/approve`.

---

## Google Cloud Project Setup

All Google APIs are used in **testing mode** (≤ 100 test users, no Google verification required).

### 1. Create a project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → **New project** → give it a name (e.g. `axolotl-dev`).
2. Enable these APIs (search each in **APIs & Services → Library**):
   - **Gmail API**
   - **Google Calendar API**
   - **Google People API** (needed for profile/email on OAuth)

### 2. Configure the OAuth consent screen

1. **APIs & Services → OAuth consent screen**
2. User type: **External** → Create
3. Fill in:
   - App name: `Axolotl`
   - User support email: your email
   - Developer contact: your email
4. **Scopes** → Add scopes:
   - `openid`, `email`, `profile`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/calendar.events`
5. **Test users** → Add the Google accounts you'll log in with during development (required while the app is in testing mode).
6. Save.

### 3. Create OAuth credentials

1. **APIs & Services → Credentials → Create credentials → OAuth client ID**
2. Application type: **Web application**
3. Name: `axolotl-web`
4. **Authorized redirect URIs** — add:
   ```
   http://localhost:8000/auth/callback
   ```
5. Click **Create** → copy **Client ID** and **Client Secret**.

### 4. Create an API key for Gemini

1. **APIs & Services → Credentials → Create credentials → API key**
2. Copy the key. (Restrict it to `Generative Language API` for safety.)

---

## Environment Variables

Create `backend/.env`:

```env
# ── Gemini ─────────────────────────────────────────────────────────────────
GOOGLE_API_KEY=AIza...           # Gemini / Generative Language API key

# ── Google OAuth ──────────────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# ── JWT ────────────────────────────────────────────────────────────────────
JWT_SECRET=change-me-in-production-use-a-long-random-string

# ── Tavily (web search) ───────────────────────────────────────────────────
TAVILY_API_KEY=tvly-...

# ── Optional overrides ─────────────────────────────────────────────────────
# DATABASE_URL=sqlite:///./axolotl.db    (default)
# DEV_MODE=false                         (set true to allow X-User-Id header)
# FRONTEND_URL=http://localhost:5173     (default)
# NUDGE_RATE_CAP=5                       (max nudges per user per day)
# NUDGE_QUIET_HOURS_START=22             (UTC hour — quiet starts)
# NUDGE_QUIET_HOURS_END=8               (UTC hour — quiet ends)
```

---

## Running locally

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

On first start, `init_db()` creates all tables including `proposed_actions` and `nudges`.

### Frontend

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

Vite proxies all API calls to `localhost:8000` — no CORS config needed in dev.

---

## Demo walkthrough

1. **Sign in** — click "Sign in with Google". After OAuth you land back at the app with a JWT.

2. **Login briefing** — Jarvis fetches your calendar and inbox, synthesises a greeting + today's agenda, and pre-drafts email replies. These appear as cards in the "Needs your approval" panel on the right.

3. **Chat with Jarvis** — try:
   - _"What's in my inbox?"_ → Schedule Agent reads Gmail, proposes replies.
   - _"Any meetings today?"_ → Calendar Agent shows today's events.
   - _"Find me potential co-founders in climate tech"_ → Web Agent searches; Connection Agent scans matches.
   - _"Draft a reply to the email from Alex"_ → email reply card appears in the approval panel.

4. **Approve actions** — each card in the "Needs your approval" panel has one-click approve:
   - **Email reply** — review/edit the body, click "↑ Send reply" → Gmail API sends it.
   - **Calendar event** — review details, click "✓ Add to calendar" → Calendar API creates it.
   - **Connection proposal** — review the match briefing and A2A negotiation transcript, click "✓ Connect" → marks mutual approval (contact exchange is a TODO pending mutual-consent implementation).

5. **Nudges** — the nudge engine runs every 30 min, checks for new unread emails, imminent meetings, and new connection matches, and shows dismissable alerts at the bottom-left of the Jarvis hub.

6. **Connection panel** — the Connections tab on the right shows all matchmaker briefings. The matchmaker runs every 60 min automatically; you can also ask Jarvis to "find me connections" on demand.

---

## Out of scope (TODOs in code)

- **Mutual-consent contact exchange** — `models.py` + `api/proposed_actions.py` both carry the TODO. Status reaching `approved` does not yet exchange contact details; the secure exchange mechanism is not implemented.
- Real cross-deployment A2A over HTTP / signed agent cards
- Real embeddings model (column reserved in `agent_cards`)
- Google app verification for public Gmail/Calendar (testing mode only, 100-user cap)
- B2A advertising layer and reputation/trust scoring
- Per-user timezone support for quiet hours (currently UTC)
