"""Tokens (Ed25519 JWT, RFC 8693 exchange), the tamper-evident audit ledger and benchmark results."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from ..core import tokens
from ..core.engine import claims_short
from ..deps import get_hub, not_found, require_key
from ..schemas import ExchangeIn
from ..services import store
from ..services.hub import Hub

router = APIRouter(prefix="/api", tags=["security"], dependencies=[Depends(require_key)])
DATA = Path(__file__).resolve().parents[2] / "data"


@router.get("/tokens/{aid}", summary="An agent's current and previous token claims")
def token(aid: str, hub: Hub = Depends(get_hub)):
    a = hub.engine.agents.get(aid)
    if not a: raise not_found("agent")
    return dict(current=claims_short(a.token), previous=claims_short(a.token_prev), token=a.token, jwt_header=dict(alg="EdDSA", typ="JWT"), revoked_count=len(tokens.REVOKED))


@router.post("/token/exchange", summary="RFC 8693 token exchange: scope can only shrink")
def exchange(x: ExchangeIn, hub: Hub = Depends(get_hub)):
    a = hub.engine.agents.get(x.agent)
    if not a: raise not_found("agent")
    try:
        r = tokens.exchange(a.token, x.scope, x.ttl, a.level)
    except ValueError as e:
        raise HTTPException(400, str(e))
    a.token_prev = a.token; a.token = r["access_token"]; a.token_scopes = r["scope"].split()
    return r


@router.get("/jwks", summary="Public key for verifying gateway tokens")
def jwks():
    return dict(alg="EdDSA", pem=tokens.public_pem())


@router.get("/audit", summary="Latest ledger records")
def audit(limit: int = 30):
    return store.audit_list(limit)


@router.get("/audit/verify", summary="Verify the whole hash chain")
def audit_verify():
    return store.audit_verify()


@router.post("/audit/tamper", summary="Demo: silently edit an old record to show detection")
def audit_tamper():
    return store.audit_tamper()


@router.post("/audit/reseal", summary="Recompute hashes after an investigation")
def audit_reseal():
    return store.audit_rebuild()


@router.get("/benchmarks", summary="Results of the research simulation (synthetic traces)")
def benchmarks():
    r = json.loads((DATA / "results.json").read_text())
    roc = lambda k: dict(auc=r["roc"][k]["auc"], fpr=r["roc"][k]["fpr"][::3], tpr=r["roc"][k]["tpr"][::3])
    return dict(scen=r["scen"], roc=dict(ml=roc("ml"), dw=roc("dw")), fpr=r["fpr"], cold=r["cold"], drift=dict(ml=r["drift"]["ml"], dw=r["drift"]["dw"], example=r["drift"]["example"]),
                latency=r["latency"], note="Synthetic traces from research/sim.py; re-measure on live traces.")
