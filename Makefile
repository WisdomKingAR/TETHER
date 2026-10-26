.PHONY: dev test build serve lint
dev:        ## backend + frontend with hot reload
	./start.sh
test:       ## backend tests (engine + API)
	cd backend && python3 -m pytest
build:      ## production front-end bundle (commit frontend/dist for one-service hosting)
	cd frontend && npm ci && npm run build
serve:      ## one process serves API, WebSocket and the built UI on :8000
	cd backend && python3 -m uvicorn driftward.main:app --port 8000
lint:
	cd backend && python3 -m ruff check driftward
