# Axolot Frontend (React + Vite + TS)

## Run locally

```bash
npm install
npm run dev          # http://localhost:5173
```

Dev proxies `/api` → `http://localhost:8000` (see `vite.config.ts`), so no env
file is needed for local dev. For a deployed build set `VITE_BACKEND_URL` to
the backend origin (see `.env.example`).

## Build

```bash
npm run build        # tsc -b && vite build
```

## Layout

- `src/pages/` — routes   `src/components/` — UI
- `src/lib/api.ts` — single API client (auth + token refresh)
- `src/styles/tokens.css` — Biopunk design tokens
