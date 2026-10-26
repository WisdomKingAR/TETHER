"""TETHER gateway. Run from backend/:  uvicorn driftward.main:app --port 8000

In production the same process also serves the built front end (frontend/dist), so one service hosts everything."""
from __future__ import annotations
import logging, os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import api_router, ws_router
from .config import settings
from .deps import set_hub
from .logging_setup import RequestContext, log, setup_logging
from .services import store
from .services.hub import Hub

TAGS = [
    {"name": "live", "description": "Event stream, health, metrics and simulation controls."},
    {"name": "agents", "description": "Agents, cold-start spawning, operator actions, delegation graph."},
    {"name": "alerts", "description": "Scored events, incidents, approvals, coverage and SIEM export."},
    {"name": "contracts", "description": "Signed Role Contracts: what-if replay and versioned deploys."},
    {"name": "attacks", "description": "Attack scenarios, prompt-injection playground, decoy sandbox, canary tripwire."},
    {"name": "security", "description": "Tokens (RFC 8693), tamper-evident audit ledger, benchmarks."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    hub = Hub()
    hub.autopilot = settings.autopilot
    hub.autopilot_interval = settings.autopilot_interval
    hub.start()
    set_hub(hub)
    log.info("TETHER %s ready: %d agents, env=%s, auth=%s", __version__, len(hub.engine.agents), settings.env, "api-key" if settings.api_key else "open")
    try:
        yield
    finally:
        for t in list(hub.tasks) + list(hub.loops.values()):
            t.cancel()
        store.flush()               # never lose queued events/ledger records on shutdown
        set_hub(None)
        log.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="TETHER", version=__version__, lifespan=lifespan, openapi_tags=TAGS,
                  description="Detects when an AI agent's behaviour drifts from its declared role while its credentials stay valid.")
    app.add_middleware(RequestContext)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "X-Process-Time"])
    app.include_router(api_router)
    app.include_router(ws_router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logging.getLogger("tether").exception("unhandled %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "internal error"}, status_code=500)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built single-page app (if present) from the same origin as the API."""
    dist = Path(os.environ.get("FRONTEND_DIST") or Path(__file__).resolve().parents[2] / "frontend" / "dist")
    index = dist / "index.html"
    if not index.exists():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith(("api/", "ws")):
            return JSONResponse({"detail": "not found"}, status_code=404)
        f = dist / path
        return FileResponse(f if path and f.is_file() else index)


app = create_app()
