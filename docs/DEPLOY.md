# Deploying TETHER

TETHER needs a **long-running process** (WebSocket stream, background traffic loops, in-memory state). That rules out serverless hosts such as Vercel Functions for the **backend**. Two options:

## Option A: Render only (recommended, one service)

The FastAPI process serves the API, the WebSocket and the built UI (`frontend/dist`, committed) from one address. No CORS, no extra URLs.

In Render: **New → Web Service → connect your repo**, then:

| Field | Value |
|---|---|
| Name | `tether` |
| Language | Python 3 |
| Branch | `main` |
| Root Directory | *(leave empty)* |
| Build Command | `pip install -r backend/requirements.txt` |
| Start Command | `cd backend && uvicorn driftward.main:app --host 0.0.0.0 --port $PORT` |
| Instance type | **Free** |
| Health Check Path (Advanced) | `/api/health` |

Environment variables:

| Key | Value | Why |
|---|---|---|
| `PYTHON_VERSION` | `3.12.7` | pins a Python that has wheels for numpy/cryptography |
| `TETHER_ENV` | `production` | shown in `/api/health` |
| `TETHER_AUTOPILOT` | `1` | the demo keeps launching attacks, so visitors see action |
| `CORS_ORIGINS` | `*` | fine for a demo; restrict if you add a custom domain |

Or use the included **`render.yaml`** (New → Blueprint) which sets all of the above.

**Free-tier behaviour:** the service sleeps after ~15 minutes without traffic and takes ~30-60 s to wake. State is in memory/SQLite on an ephemeral disk, so it resets on each wake or deploy. That is fine for a demo; the UI reconnects its WebSocket automatically.

Update the UI bundle before pushing UI changes: `cd frontend && npm ci && npm run build` and commit `frontend/dist`.

## Option B: Deploying on Vercel

### Full-Stack Vercel Monorepo Deployment
The repository includes root configuration (`vercel.json`, `requirements.txt`, and `api/index.py`) so you can deploy directly:
1. In Vercel: **Add New → Project → import the repo**.
2. Leave **Root Directory** as default (`.`).
3. Vercel automatically builds the frontend (`frontend/dist`), routes `/api/*` to the Python FastAPI serverless function (`api/index.py`), and routes all UI pages to the SPA.
4. (Optional) If connecting to a standalone long-running backend with continuous WebSockets, set `VITE_API_URL=https://<your-service>.onrender.com`.

### Frontend Only on Vercel (UI + Render API)
1. Deploy the backend on Render as in Option A.
2. In Vercel: **Add New → Project → import the repo**, set **Root Directory = `frontend`**.
3. Add environment variable `VITE_API_URL=https://<your-service>.onrender.com`.
4. The UI derives the WebSocket URL (`wss://…/ws`) from `VITE_API_URL`.

## Hardening checklist (if you keep it public)

- Set `TETHER_API_KEY` to require `X-API-Key` on every POST/PUT/DELETE (the demo UI does not send one, so only do this for API-only use).
- Restrict `CORS_ORIGINS`.
- Put a rate limiter or the host's WAF in front; the public demo exposes attack-simulation endpoints.
