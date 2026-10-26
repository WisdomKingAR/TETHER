"""Runtime settings, read once from environment variables (see .env.example)."""
from __future__ import annotations
import os
from dataclasses import dataclass, field


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "8000"))
    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS", "*"))
    api_key: str | None = os.environ.get("TETHER_API_KEY") or None
    db_path: str | None = os.environ.get("TETHER_DB") or None
    autopilot: bool = os.environ.get("TETHER_AUTOPILOT", "0") == "1"
    autopilot_interval: float = float(os.environ.get("TETHER_AUTOPILOT_INTERVAL", "14"))
    env: str = os.environ.get("TETHER_ENV", "development")


settings = Settings()
