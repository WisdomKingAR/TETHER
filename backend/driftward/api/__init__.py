"""HTTP API: one router per domain."""
from fastapi import APIRouter

from . import agents, alerts, attacks, contracts, live, security

api_router = APIRouter()
for module in (live, agents, alerts, contracts, attacks, security):
    api_router.include_router(module.router)
ws_router = live.ws_router
