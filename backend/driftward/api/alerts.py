"""Events, alerts, approvals, coverage and SIEM export."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from ..deps import get_hub, must, not_found, require_key
from ..schemas import ApprovalIn
from ..services import store
from ..services.hub import Hub

router = APIRouter(prefix="/api", tags=["alerts"], dependencies=[Depends(require_key)])


@router.get("/events", summary="Recent scored events")
def events(limit: int = Query(100, ge=1, le=1000), agent: str | None = None, flagged: bool = False):
    return [dict(id=o["event"]["id"], ts=o["event"]["ts"], agent=o["event"]["agent"], tool=o["event"]["tool"], target=o["event"].get("target") or o["event"].get("egress", ""),
                 risk=o["risk"], verdict=o["verdict"], level=o["level_name"]) for o in store.recent_events(limit, agent, flagged)]


@router.get("/events/{eid}", summary="Full event with per-plane scores and reasons")
def event_detail(eid: int):
    return must(store.get_event(eid), "event")


@router.get("/alerts", summary="Incidents, newest first")
def alerts(hub: Hub = Depends(get_hub)):
    return sorted(hub.engine.alerts.values(), key=lambda a: -a["opened"])


@router.get("/alerts/{aid}", summary="One incident: causal chain, plane contributions, token change")
def alert(aid: str, hub: Hub = Depends(get_hub)):
    return must(hub.engine.alerts.get(aid), "alert")


@router.get("/alerts/{aid}/report", response_class=PlainTextResponse, summary="Incident report as markdown")
def report(aid: str, hub: Hub = Depends(get_hub)):
    if aid not in hub.engine.alerts: raise not_found("alert")
    return hub.engine.report(aid)


@router.get("/timeline", summary="Per-agent risk series")
def timeline(n: int = Query(120, ge=1, le=600), hub: Hub = Depends(get_hub)):
    return {r: [dict(id=h["event"]["id"], ts=h["event"]["ts"], risk=h["agent_risk"], ev=h["risk"], level=h["level"]) for h in list(a.history)[-n:]] for r, a in hub.engine.agents.items()}


@router.get("/coverage", summary="OWASP Agentic Top 10 coverage with live hit counts")
def coverage(hub: Hub = Depends(get_hub)):
    return hub.engine.coverage()


@router.get("/approvals", summary="Human-in-the-loop queue: held actions and recent decisions")
def approvals(hub: Hub = Depends(get_hub)):
    return dict(pending=list(hub.engine.pending.values()), resolved=hub.engine.resolved[:15])


@router.post("/approvals/{eid}", summary="Approve or deny a held action (written to the audit ledger)")
async def approval(eid: int, a: ApprovalIn, hub: Hub = Depends(get_hub)):
    p = hub.engine.resolve(eid, a.approve)
    if not p: raise not_found("pending action")
    store.audit_append(dict(event=eid, agent=p["agent"], tool=p["tool"], target=p["target"], risk=p["risk"], verdict="HUMAN_" + p["status"].upper(), level="step-up",
                            contract=hub.engine.agents[p["agent"]].contract["version"]))
    await hub.broadcast(dict(type="approval", item=p, agent=hub.engine.agents[p["agent"]].public()))
    return p


@router.get("/siem/cef", response_class=PlainTextResponse, summary="Recent events in CEF for Splunk/Elastic ingestion")
def siem_cef(limit: int = Query(40, ge=1, le=500)):
    lines = []
    for o in reversed(store.recent_events(limit)):
        ev = o["event"]; fired = [k for k, v in o["planes"].items() if v["score"] > 0.5]
        sev = 10 if o["risk"] >= 90 else 8 if o["risk"] >= 70 else 5 if o["risk"] >= 50 else 3 if o["risk"] >= 30 else 1
        lines.append(f"CEF:0|TETHER|Gateway|1.0|{','.join(fired) or 'allow'}|{ev['tool']}|{sev}|suser={ev['agent']} act={o['verdict']} cs1={o['level_name']} cn1={o['risk']} dhost={ev.get('egress') or '-'} fsize={int(ev.get('bytes', 0))}")
    return "\n".join(lines)
