#!/usr/bin/env bash
# Local dev: FastAPI gateway on :8000 and the Vite UI on :5173. No Docker, no external services.
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v node >/dev/null || { echo "node is required"; exit 1; }
python3 -m pip install -q -r backend/requirements.txt
[ -d frontend/node_modules ] || (cd frontend && npm install --no-audit --no-fund)
mkdir -p backend/data
(cd backend && exec python3 -m uvicorn driftward.main:app --reload --port 8000) & API=$!
(cd frontend && exec npx vite --port 5173) & WEB=$!
trap 'kill $API $WEB 2>/dev/null' EXIT INT TERM
echo; echo "  Console  ->  http://localhost:5173"; echo "  API docs ->  http://localhost:8000/docs"; echo
wait
