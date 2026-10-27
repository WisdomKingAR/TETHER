"""Live stream, health, metrics and simulation controls."""
from __future__ import annotations
import asyncio as _asyncio
import json as _json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from .. import __version__
from ..config import settings
from ..core.engine import LEVELS
from ..deps import get_hub, require_key
from ..schemas import AutoIn, Health, ModeIn, Ok, SimIn
from ..services.hub import Hub

ws_router = APIRouter()
router = APIRouter(prefix="/api", tags=["live"], dependencies=[Depends(require_key)])


@ws_router.websocket("/ws")
async def stream(sock: WebSocket, hub: Hub = Depends(get_hub)):
    """Every scored event, alert, agent change and attack-run step, as JSON messages."""
    await hub.connect(sock)
    try:
        while True:
            await sock.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(sock)


@router.get("/health", response_model=Health, summary="Liveness and basic counters")
def health(hub: Hub = Depends(get_hub)):
    return Health(ok=True, version=__version__, env=settings.env, agents=len(hub.engine.agents), events=hub.engine.eid, clients=len(hub.clients), mode="enforce" if hub.engine.enforce else "shadow")


@router.get("/ready", summary="Readiness probe (gateway started)")
def ready(hub: Hub = Depends(get_hub)):
    return {"ready": True}


@router.get("/metrics", summary="Engine and pipeline latency percentiles, throughput, DB queue")
def metrics(hub: Hub = Depends(get_hub)):
    return hub.metrics()


@router.get("/state", summary="Snapshot of all agents plus simulation flags")
def state(hub: Hub = Depends(get_hub)):
    s = hub.engine.snapshot()
    s.update(paused=hub.paused, speed=hub.speed, levels=LEVELS, autopilot=hub.autopilot, pending=len(hub.engine.pending))
    return s


@router.post("/mode", summary="Switch between enforce and shadow (observe-only) mode")
async def mode(m: ModeIn, hub: Hub = Depends(get_hub)):
    hub.engine.enforce = m.enforce
    await hub.broadcast(dict(type="mode", enforce=m.enforce))
    return dict(enforce=m.enforce)


@router.post("/sim", summary="Pause or speed up the simulated benign traffic")
async def sim(s: SimIn, hub: Hub = Depends(get_hub)):
    if s.paused is not None: hub.paused = s.paused
    if s.speed is not None: hub.speed = s.speed
    await hub.broadcast(dict(type="sim", paused=hub.paused, speed=hub.speed))
    return dict(paused=hub.paused, speed=hub.speed)


@router.post("/autopilot", summary="Red-team autopilot: launch random attacks on a timer")
async def autopilot(a: AutoIn, hub: Hub = Depends(get_hub)):
    hub.autopilot = a.on
    if a.interval: hub.autopilot_interval = a.interval
    await hub.broadcast(dict(type="autopilot", on=hub.autopilot))
    return dict(on=hub.autopilot, interval=hub.autopilot_interval, log=hub.autopilot_log)


@router.post("/tick", summary="Simulate one benign traffic tick across agents")
async def sim_tick(hub: Hub = Depends(get_hub)):
    """Triggers one benign event cycle. Useful for driving live telemetry on serverless deployments."""
    if not hub.paused:
        active = [r for r, a in hub.engine.agents.items() if a.level < 4]
        if active:
            role = hub.rng.choice(active)
            ev = hub.benign_event(role)
            msg = await hub.emit(ev)
            return dict(ok=True, event=msg, counts=hub.engine.snapshot()["counts"])
    return dict(ok=True, counts=hub.engine.snapshot()["counts"])


@router.post("/reset", response_model=Ok, summary="Reset all demo state (agents, alerts, ledger)")
async def reset(hub: Hub = Depends(get_hub)):
    await hub.reset()
    return Ok()


@router.get("/stream", summary="SSE event stream — serverless-compatible fallback for /ws")
async def sse_stream(hub: Hub = Depends(get_hub)):
    """Server-Sent Events endpoint. Sends the same messages as /ws.
    Used automatically by the frontend when WebSocket is unavailable (e.g. Vercel)."""

    async def generator():
        import asyncio
        # Immediately send the hello snapshot
        snap = hub.engine.snapshot()
        hello = dict(
            type="hello",
            autopilot=hub.autopilot,
            pending=list(hub.engine.pending.values()),
            snapshot=snap,
            tail=hub.history_tail[-120:],
            runs=list(hub.runs.values())[-5:],
        )
        yield f"data: {_json.dumps(hello, default=str)}\n\n"

        q: asyncio.Queue = asyncio.Queue(maxsize=400)
        hub.sse_clients.add(q)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {_json.dumps(msg, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"   # prevent proxy / CDN from closing idle connection
        finally:
            hub.sse_clients.discard(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
