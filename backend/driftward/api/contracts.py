"""Role Contracts: read, what-if replay, learn from traces, sign a new version."""
from __future__ import annotations
from fastapi import APIRouter, Depends

from ..core.roles import ROLES
from ..deps import get_hub, not_found, require_key
from ..schemas import ContractPatch
from ..services.hub import Hub

router = APIRouter(prefix="/api", tags=["contracts"], dependencies=[Depends(require_key)])


@router.get("/contracts", summary="All current contracts")
def contracts(hub: Hub = Depends(get_hub)):
    return {r: a.contract for r, a in hub.engine.agents.items()}


@router.get("/contracts/{aid}", summary="One contract plus the agent's tool catalogue")
def contract(aid: str, hub: Hub = Depends(get_hub)):
    a = hub.engine.agents.get(aid)
    if not a: raise not_found("agent")
    return dict(contract=a.contract, catalog=[dict(name=t[0], cls=t[1], sink=bool(t[3])) for t in ROLES[aid]["tools"]])


@router.put("/contracts/{aid}", summary="Sign and deploy a new contract version (opens a 5-minute canary window)")
async def put_contract(aid: str, patch: ContractPatch, hub: Hub = Depends(get_hub)):
    if aid not in hub.engine.agents: raise not_found("agent")
    c = hub.engine.set_contract(aid, patch.model_dump(exclude_none=True))
    await hub.broadcast(dict(type="agent", agent=hub.engine.agents[aid].public()))
    return c


@router.post("/contracts/{aid}/whatif", summary="Replay the last 300 real events against a proposed contract")
def whatif(aid: str, patch: ContractPatch, hub: Hub = Depends(get_hub)):
    if aid not in hub.engine.agents: raise not_found("agent")
    return hub.engine.whatif(aid, patch.model_dump(exclude_none=True))


@router.post("/contracts/{aid}/suggest", summary="Draft a contract from observed clean behaviour")
def suggest(aid: str, hub: Hub = Depends(get_hub)):
    if aid not in hub.engine.agents: raise not_found("agent")
    return hub.engine.suggest(aid)
