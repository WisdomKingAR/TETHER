"""HTTP/WebSocket integration tests against the real FastAPI app. Run: cd backend && python -m pytest -q"""
import os, sys, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["TETHER_DB"] = os.path.join(tempfile.gettempdir(), "tether_api_test.db")

import pytest
from fastapi.testclient import TestClient

from driftward.main import create_app


@pytest.fixture(scope="module")
def c():
    with TestClient(create_app()) as client:
        client.post("/api/sim", json={"speed": 8})
        yield client


def wait_run(c, run_id, timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = next(x for x in c.get("/api/runs").json() if x["id"] == run_id)
        if r["status"] == "done": return r
        time.sleep(0.3)
    raise AssertionError("run did not finish")


def test_health_ready_and_headers(c):
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] and r.json()["agents"] == 5
    assert "x-request-id" in r.headers and r.headers["x-process-time"].endswith("ms")
    assert c.get("/api/ready").json() == {"ready": True}


def test_state_agents_and_404(c):
    assert len(c.get("/api/agents").json()) >= 5
    assert c.get("/api/agents/procurement").json()["contract"]["version"] >= 1
    assert c.get("/api/agents/nope").status_code == 404
    assert c.get("/api/alerts/A-0").status_code == 404


def test_validation_errors_are_422(c):
    assert c.post("/api/sim", json={"speed": 99}).status_code == 422
    assert c.post("/api/attack", json={}).status_code == 422
    assert c.post("/api/canary/check", json={"value": "x"}).status_code == 422


def test_injection_attack_end_to_end(c):
    c.post("/api/reset"); time.sleep(0.5)
    run = c.post("/api/attack", json={"scenario": "injection"}).json()
    done = wait_run(c, run["id"])
    s = done["summary"]
    assert s["leaked_bytes"] == 0 and s["iam_only_would_leak"] > 0 and s["final_level"] == 3
    al = c.get(f"/api/alerts/{s['alert']}").json()
    assert al["chain"] and al["planes"]["p1"] > 0
    assert "Causal chain" in c.get(f"/api/alerts/{al['id']}/report").text
    assert c.get(f"/api/events/{al['chain'][-1]['id']}").json()["event"]["agent"] == "procurement"
    assert any(x["hits"] > 0 for x in c.get("/api/coverage").json()["owasp"])
    assert c.get("/api/siem/cef").text.startswith("CEF:0|TETHER")
    sb = c.get("/api/sandbox").json()
    assert "procurement" in sb and sb["procurement"]["entries"]


def test_canary_tripwire_isolates(c):
    canary = c.get("/api/canaries").json()[-1]["canary"]
    r = c.post("/api/canary/check", json={"value": f"AKIA{canary.upper()}CANARY"}).json()
    assert r["found"] and c.get(f"/api/agents/{r['agent']}").json()["level"] == 4
    assert c.post("/api/canary/check", json={"value": "AKIA-NOT-OURS-123"}).json()["found"] is False
    c.post(f"/api/agents/{r['agent']}/release")


def test_contract_whatif_and_versioning(c):
    before = c.get("/api/contracts/hr_help").json()["contract"]["version"]
    w = c.post("/api/contracts/hr_help/whatif", json={"allow_tools": ["kb.search"]}).json()
    assert w["fires_after"] >= w["fires_before"]
    put = c.put("/api/contracts/hr_help", json={"rate_per_min": 150}).json()
    assert put["version"] == before + 1 and put["signature"].startswith("ed25519:") and put["canary_until"]


def test_token_exchange_only_narrows(c):
    t = c.get("/api/tokens/finance_recon").json()
    scopes = t["current"]["scope"]
    r = c.post("/api/token/exchange", json={"agent": "finance_recon", "scope": scopes[:2] + ["root.everything"], "ttl": 120})
    assert r.status_code == 200 and "root.everything" not in r.json()["scope"]
    assert c.get("/api/jwks").json()["alg"] == "EdDSA"


def test_grayzone_approval_flow(c):
    run = c.post("/api/attack", json={"scenario": "grayzone"}).json(); wait_run(c, run["id"])
    q = c.get("/api/approvals").json()
    assert q["pending"], "a held action should be waiting for a human"
    eid = q["pending"][0]["id"]
    assert c.post(f"/api/approvals/{eid}", json={"approve": False}).json()["status"] == "denied"
    assert c.post(f"/api/approvals/{eid}", json={"approve": False}).status_code == 404


def test_cold_start_spawn_and_delete(c):
    a = c.post("/api/agents", json={"template": "procurement"}).json()
    assert a["cold"] and a["spawned"]
    run = c.post("/api/attack", json={"scenario": "injection", "agent": a["id"]}).json()
    assert wait_run(c, run["id"])["summary"]["leaked_bytes"] == 0
    assert c.delete(f"/api/agents/{a['id']}").status_code == 200
    assert c.delete("/api/agents/procurement").status_code == 400


def test_audit_ledger_tamper_detection(c):
    time.sleep(1.5)     # let the write-behind queue flush
    assert c.get("/api/audit/verify").json()["ok"]
    if c.post("/api/audit/tamper").json().get("ok"):
        assert not c.get("/api/audit/verify").json()["ok"]
        c.post("/api/audit/reseal"); assert c.get("/api/audit/verify").json()["ok"]


def test_metrics_and_benchmarks(c):
    m = c.get("/api/metrics").json()
    assert m["events_total"] > 0 and m["engine_us"]["p50"] > 0
    assert c.get("/api/benchmarks").json()["fpr"]["dw"] < 0.02


def test_websocket_hello_and_events(c):
    with c.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and len(hello["snapshot"]["agents"]) >= 5
        seen = {ws.receive_json()["type"] for _ in range(6)}
        assert "event" in seen


def test_api_key_protects_mutations():
    from driftward import deps
    object.__setattr__(deps.settings, "api_key", "secret")      # Settings is a frozen dataclass; restore in finally
    try:
        with TestClient(create_app()) as k:
            assert k.get("/api/health").status_code == 200
            assert k.post("/api/mode", json={"enforce": True}).status_code == 401
            assert k.post("/api/mode", json={"enforce": True}, headers={"X-API-Key": "secret"}).status_code == 200
    finally:
        object.__setattr__(deps.settings, "api_key", None)
