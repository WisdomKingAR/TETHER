"""Attack scenarios, the prompt-injection playground, the decoy sandbox and the canary tripwire."""
from __future__ import annotations
from fastapi import APIRouter, Depends

from ..core import scenarios
from ..deps import get_hub, not_found, require_key
from ..schemas import AttackIn, CanaryIn, PlayIn
from ..services import store
from ..services.hub import Hub, compact

router = APIRouter(prefix="/api", tags=["attacks"], dependencies=[Depends(require_key)])


@router.get("/scenarios", summary="Attack scenario catalogue")
def scenario_list():
    return scenarios.CATALOG


@router.post("/attack", summary="Launch an attack scenario against the live engine")
async def attack(a: AttackIn, sync: bool = False, hub: Hub = Depends(get_hub)):
    if a.scenario not in scenarios.BY_ID: raise not_found("scenario")
    if a.agent and a.agent not in hub.engine.agents: raise not_found("agent")
    return await hub.start_run(a.scenario, a.agent, sync=sync)


@router.post("/playground", summary="Let an agent read pasted text and obey hidden instructions")
async def playground(p: PlayIn, sync: bool = False, hub: Hub = Depends(get_hub)):
    if p.agent not in hub.engine.agents: raise not_found("agent")
    steps = scenarios.playground_steps(p.agent, p.text, hub.engine)
    return await hub.start_run("playground", p.agent, steps=steps, title="Your pasted document", sync=sync)


@router.get("/runs", summary="Recent attack runs with summaries")
def runs(hub: Hub = Depends(get_hub)):
    return list(hub.runs.values())[-20:]


@router.get("/runs/{run_id}", summary="Get a specific attack run with all its steps and telemetry")
def run_detail(run_id: str, hub: Hub = Depends(get_hub)):
    r = hub.runs.get(run_id)
    if not r: raise not_found("run")
    return r


@router.get("/sandbox", summary="Decoy-sandbox sessions: what the attacker saw vs what we recorded")
def sandbox(hub: Hub = Depends(get_hub)):
    return {r: dict(agent=a.public(), entries=a.sandbox[-25:]) for r, a in hub.engine.agents.items() if a.sandbox}


@router.get("/canaries", summary="Canary credentials issued by the sandbox")
def canaries(hub: Hub = Depends(get_hub)):
    return [dict(canary=c, agent=a) for c, a in list(hub.engine.canaries.items())[-12:]]


@router.post("/canary/check", summary="Report a canary sighting: confirms exfiltration and isolates the agent")
async def canary(c: CanaryIn, hub: Hub = Depends(get_hub)):
    r = hub.engine.confirm_canary(c.value)
    if r["found"]:
        a = hub.engine.agents[r["agent"]]
        msg = compact(r.pop("out")); store.save_event(a.history[-1])
        await hub.broadcast(msg)
        al = hub.engine.alerts.get(a.incident) or max(hub.engine.alerts.values(), key=lambda x: x["opened"])
        store.save_alert(al); await hub.broadcast(dict(type="alert", alert=al, new=False))
        r["alert"] = al["id"]
    return r
