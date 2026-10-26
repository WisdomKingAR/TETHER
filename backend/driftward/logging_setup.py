"""Structured one-line logging and a request-timing middleware."""
from __future__ import annotations
import logging, time, uuid
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings


def setup_logging() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # we log requests ourselves, with timing


log = logging.getLogger("tether")


class RequestContext(BaseHTTPMiddleware):
    """Adds X-Request-ID and X-Process-Time, and logs mutating or slow requests."""

    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:10]
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error rid=%s %s %s", rid, request.method, request.url.path)
            raise
        ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time"] = f"{ms:.1f}ms"
        if request.method != "GET" or ms > 150:
            log.info("%s %s -> %s %.1fms rid=%s", request.method, request.url.path, response.status_code, ms, rid)
        return response
