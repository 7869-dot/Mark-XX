# Axolot Backend (FastAPI)

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in values
uvicorn app.main:app --reload
```

The app entrypoint is `app/main:app` (not `main:app`). Tables auto-create on
startup; APScheduler jobs register automatically. Set `USE_STUBS=true` in
`.env` to run with no Google/Gemini/Postgres credentials (uses SQLite + canned
data).

## Layout

- `app/api/` — routers   `app/services/` — business logic
- `app/models/` — SQLAlchemy   `app/scheduler/` — proactive jobs
- `alembic/` — DB migrations
