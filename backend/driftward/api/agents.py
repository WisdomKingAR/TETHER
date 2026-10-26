"""Agents: listing, spawning cold-start agents, operator actions, delegation graph."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException

from ..core.roles import ROLES
from ..deps import get_hub, must, not_found, require_key
from ..schemas import Ok, SpawnIn
from ..services.hub import Hub

router = APIRouter(prefix="/api", tags=["agents"], dependencies=[Depends(require_key)])


@router.get("/agents", summary="All agents with risk, level and token scope")
def agents(hub: Hub = Depends(get_hub)):
    return [a.public() for a in hub.engine.agents.values()]


@router.post("/agents", summary="Spawn a brand-new agent with no history (day-0 protection)")
async def spawn(s: SpawnIn, hub: Hub = Depends(get_hub)):
    if s.template not in ROLES or ROLES[s.template].get("seed_role"):
        raise not_found("template")
    return await hub.spawn(s.template, s.name)


@router.get("/agents/{aid}", summary="One agent: contract, tools, recent events, learned behaviour")
def agent(aid: str, hub: Hub = Depends(get_hub)):
    a = must(hub.engine.agents.get(aid), "agent")
    d = a.public()
    d.update(tools=[dict(name=t[0], cls=t[1], sink=bool(t[3]), ingests=bool(t[4])) for t in ROLES[aid]["tools"]], contract=a.contract,
             recent=[dict(id=h["event"]["id"], tool=h["event"]["tool"], risk=h["risk"], verdict=h["verdict"]) for h in list(a.history)[-40:]],
             transition=a.T.tolist(), baseline=a.base_dist.tolist())
    return d


@router.delete("/agents/{aid}", response_model=Ok, summary="Remove a spawned agent")
async def despawn(aid: str, hub: Hub = Depends(get_hub)):
    a = hub.engine.agents.get(aid)
    if not a: raise not_found("agent")
    if not a.spawned: raise HTTPException(400, "only spawned agents can be removed")
    await hub.despawn(aid)
    return Ok()


@router.post("/agents/{aid}/release", response_model=Ok, summary="Operator releases an agent from quarantine")
async def release(aid: str, hub: Hub = Depends(get_hub)):
    if aid not in hub.engine.agents: raise not_found("agent")
    hub.engine.release(aid)
    await hub.broadcast(dict(type="agent", agent=hub.engine.agents[aid].public()))
    return Ok()


@router.post("/agents/{aid}/isolate", response_model=Ok, summary="Operator isolates an agent (L4: token revoked)")
async def isolate(aid: str, hub: Hub = Depends(get_hub)):
    if aid not in hub.engine.agents: raise not_found("agent")
    hub.engine.isolate(aid)
    await hub.broadcast(dict(type="agent", agent=hub.engine.agents[aid].public()))
    return Ok()


@router.get("/delegation", summary="Delegation graph with RFC 8693-style receipts (attenuation)")
def delegation(hub: Hub = Depends(get_hub)):
    nodes = [a.public() for a in hub.engine.agents.values()]
    edges = []
    for r, a in hub.engine.agents.items():
        if a.parent:
            p = hub.engine.agents[a.parent]
            granted = sorted(set(p.contract["allow_tools"]) & set(a.contract["allow_tools"]))
            asked = sorted(a.contract["allow_tools"])
            edges.append(dict(parent=a.parent, child=r, receipt=dict(granted=granted, requested=asked, dropped=sorted(set(asked) - set(granted)),
                                                                     subset=set(granted) <= set(p.contract["allow_tools"]), depth=1, standard="RFC 8693 actor chain")))
    return dict(nodes=nodes, edges=edges)
