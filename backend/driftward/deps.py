"""FastAPI dependencies: the shared Hub and optional API-key protection for mutating calls."""
from __future__ import annotations
from fastapi import HTTPException, Request

from .config import settings
from .services.hub import Hub

_hub: Hub | None = None


def set_hub(h: Hub | None) -> None:
    global _hub
    _hub = h


def get_hub() -> Hub:
    if _hub is None:
        raise HTTPException(503, "gateway is starting")
    return _hub


async def require_key(request: Request) -> None:
    """If TETHER_API_KEY is set, every non-GET request must carry a matching X-API-Key header."""
    if settings.api_key and request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("x-api-key") != settings.api_key:
            raise HTTPException(401, "missing or invalid X-API-Key")


def not_found(what: str = "resource") -> HTTPException:
    return HTTPException(404, f"{what} not found")


def must(value, what: str = "resource"):
    """Return value, or raise 404 when it is falsy."""
    if not value:
        raise not_found(what)
    return value
