"""Behavioural tests for the TETHER engine, tokens and audit ledger. Run: cd backend && python -m pytest -q"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["TETHER_DB"] = os.path.join(tempfile.gettempdir(), "tether_test.db")

import asyncio
import pytest
from driftward.core import scenarios, tokens
from driftward.core.engine import Engine
from driftward.services import store
from driftward.services.hub import Hub


@pytest.fixture()
def hub():
    h = Hub()
    return h


def play(engine, scenario, agent):
    out = []
    for s in scenarios.build(scenario, agent, engine):
        ev = {k: v for k, v in s.items() if k != "delay"}
        ev.setdefault("agent", agent)
        out.append(engine.process(ev))
    return out


def test_benign_traffic_stays_quiet(hub):
    for _ in range(400):
        for role in hub.engine.agents:
            hub.engine.process(hub.benign_event(role))
    assert max(a.level for a in hub.engine.agents.values()) <= 1
    assert sum(a.stats["flagged"] for a in hub.engine.agents.values()) / sum(a.stats["events"] for a in hub.engine.agents.values()) < 0.02


def test_injection_is_quarantined_and_nothing_leaks(hub):
    out = play(hub.engine, "injection", "procurement")
    a = hub.engine.agents["procurement"]
    assert a.level == 3
    assert sum(o["leaked"] for o in out) == 0
    assert out[-1]["verdict"] == "ALLOW", "in-role work must continue under quarantine"
    assert out[0]["iam"] == "ALLOW"


def test_shadow_mode_never_blocks(hub):
    hub.engine.enforce = False
    out = play(hub.engine, "injection", "procurement")
    assert all(not o["verdict"] in ("DENY", "SANDBOX", "CLIP", "ISOLATE", "REVOKE", "CLIP_HELD") for o in out)
    assert sum(o["leaked"] for o in out) > 0


@pytest.mark.parametrize("scenario,agent", [("tool_poison", "code_review"), ("token_replay", "finance_recon"), ("mimicry", "hr_help"), ("subagent", "pricing")])
def test_hard_plane_scenarios_flag_before_exfiltration(hub, scenario, agent):
    out = play(hub.engine, scenario, agent)
    assert sum(o["leaked"] for o in out) == 0
    assert hub.engine.agents[agent].level >= 3


def test_slow_drift_escalates_gradually(hub):
    out = play(hub.engine, "slow_drift", "code_review")
    levels = [o["level"] for o in out]
    assert levels[0] == 0 and max(levels) >= 2
    assert levels == sorted(levels), "drift evidence should accumulate monotonically"


def test_subagent_raises_parent_exposure(hub):
    play(hub.engine, "subagent", "pricing")
    assert hub.engine.agents["procurement"].risk > 40


def test_alert_has_causal_chain_and_narrative(hub):
    play(hub.engine, "injection", "procurement")
    al = list(hub.engine.alerts.values())[0]
    assert al["chain"] and "stopped behaving like its declared role" in al["narrative"]
    assert al["planes"]["p1"] > 0 and al["planes"]["p2"] > 0 and al["planes"]["p3"] > 0


def test_token_exchange_only_narrows():
    t = tokens.issue("procurement", ["price.read", "email.send"], 3600)
    r = tokens.exchange(t, ["price.read", "hr.dump"], 300)
    assert r["scope"].split() == ["price.read"]
    ok, _ = tokens.verify(t)
    assert not ok, "subject token is revoked after exchange"


def test_whatif_detects_new_flags(hub):
    for _ in range(150):
        hub.engine.process(hub.benign_event("procurement"))
    res = hub.engine.whatif("procurement", {"allow_tools": ["price.read"]})
    assert res["fires_after"] > res["fires_before"] and res["newly_blocked"] > 0


def test_audit_chain_detects_tampering(hub):
    for _ in range(12):
        asyncio.run(hub.emit(hub.benign_event("hr_help")))
    assert store.audit_verify()["ok"]
    assert store.audit_tamper()["ok"]
    assert not store.audit_verify()["ok"]
    store.audit_rebuild()
    assert store.audit_verify()["ok"]


def test_grayzone_is_held_for_a_human_then_resolved(hub):
    play(hub.engine, "grayzone", "hr_help")
    assert len(hub.engine.pending) >= 1 and hub.engine.agents["hr_help"].level == 1
    eid = next(iter(hub.engine.pending))
    assert hub.engine.resolve(eid, False)["status"] == "denied" and eid not in hub.engine.pending


def test_canary_reuse_confirms_exfiltration_and_isolates(hub):
    play(hub.engine, "injection", "procurement")
    canary = next(iter(hub.engine.canaries))
    r = hub.engine.confirm_canary(f"AKIA{canary.upper()}CANARY")
    assert r["found"] and hub.engine.agents["procurement"].level == 4
    assert not hub.engine.confirm_canary("nothing here")["found"]


def test_report_and_coverage(hub):
    play(hub.engine, "injection", "procurement")
    aid = next(iter(hub.engine.alerts))
    assert "Causal chain" in hub.engine.report(aid)
    assert any(r["hits"] > 0 for r in hub.engine.coverage()["owasp"])


def test_cold_start_agent_is_protected_on_first_call(hub):
    a = hub.engine.spawn("procurement")
    assert a.stats["events"] == 0 and a.cold
    out = play(hub.engine, "injection", a.role)
    assert sum(o["leaked"] for o in out) == 0 and hub.engine.agents[a.role].level >= 3
    hub.engine.remove(a.role)
    assert a.role not in hub.engine.agents


def test_cold_agent_benign_traffic_is_quiet(hub):
    a = hub.engine.spawn("hr_help")
    for _ in range(150):
        hub.engine.process(dict(hub.benign_event("hr_help"), agent=a.role))
    assert a.level <= 1 and a.stats["flagged"] / a.stats["events"] < 0.05


def test_batched_persistence_keeps_the_hash_chain_intact(hub):
    for _ in range(300):
        asyncio.run(hub.emit(hub.benign_event("code_review")))
    assert store.pending() > 0
    store.flush()
    assert store.pending() == 0 and store.audit_verify()["ok"] and store.audit_verify()["records"] >= 300
    m = hub.metrics()
    assert m["events_total"] >= 300 and m["engine_us"]["p50"] > 0
