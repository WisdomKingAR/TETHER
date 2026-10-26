# TETHER architecture (prototype)

Maps the six-column system diagram in the deck (slide 3) to code. Everything runs locally: **no Docker, no external services.**

```
 agents (simulated)           gateway = Hub + Engine                    state                 respond / explain            UI
 ┌──────────────────┐   ┌────────────────────────────────────┐   ┌──────────────┐   ┌─────────────────────────┐   ┌────────────┐
 │ benign Markov    │   │ P1 contract   P2 provenance (taint) │   │ SQLite       │   │ L0..L4 policy           │   │ React +    │
 │ traffic per role │──▶│ P3 decoys     P4 behaviour (Markov) │──▶│ events,      │──▶│ RFC 8693 token narrowing│──▶│ three.js   │
 │ attack scenarios │   │ P5 delegation P6 CUSUM drift        │   │ alerts,      │   │ decoy sandbox           │   │ WebSocket  │
 │ prompt playground│   │ identity proof, noisy-OR fusion     │   │ audit chain  │   │ alert explainer         │   │ + REST     │
 └──────────────────┘   └────────────────────────────────────┘   └──────────────┘   └─────────────────────────┘   └────────────┘
```

| Deck component | Prototype module | Stand-in vs production |
|---|---|---|
| Agent plane (LangGraph, CrewAI, MCP) | `driftward/services/hub.py` benign generator, `driftward/core/scenarios.py` attacks | Simulated agents emitting real tool-call events; production plugs MCP/A2A traffic in |
| Gateway / PEP | `driftward/core/engine.py` `Engine.process()`, `driftward/main.py` | FastAPI in-process; production: Envoy `ext_authz` or SDK sidecar |
| Identity | `driftward/core/tokens.py` Ed25519 JWT (EdDSA) | SPIFFE/SPIRE JWT-SVID in production |
| P1 Role contract | `Engine.evaluate()` + `core/roles.default_contract()` | typed rules from signed YAML; OPA/Cedar later |
| P2 Provenance / taint | `AgentState.taint`, `dest_from_t2` | taint set per agent session (12 calls); production tracks per context chunk |
| P3 Decoys | `contract.decoys`, `Engine.sandbox_entry()` | honey targets per agent; canary tokens |
| P4 Behaviour | bigram Markov surprise + payload z-score + new host/hour | scikit-learn IsolationForest used in the research sim (`research/sim.py`) |
| P5 Delegation | `scope_ok` + parent exposure in `Engine.process()`; `/api/delegation` | RFC 8693 actor chain |
| P6 Slow drift | CUSUM on Jensen-Shannon divergence, calibrated on a long benign run | `river` ADWIN / Page-Hinkley in production |
| Fusion | noisy-OR + hard floor 85, cap 94 (L4 needs operator or confirmed evidence) | weights tuned in research sim |
| Event bus | in-process `asyncio` + WebSocket broadcast, write-behind batch writer | Redis Streams → Kafka API |
| Registry / alerts / history | SQLite (`driftward/services/store.py`) | PostgreSQL + DuckDB → ClickHouse |
| Token service | `tokens.exchange()` RFC 8693 | Keycloak / Okta / Entra |
| Audit | hash-chained table, verify/tamper/reseal | hash chain anchored externally |
| Console | `frontend/` React, react-three-fiber, postprocessing | + Grafana, SIEM webhook |

## Request lifecycle
1. An event `{agent, tool, target, data_class, bytes, egress, taint, proof_ok, …}` reaches `Hub.emit()`.
2. `Engine.process()` scores P1–P6 + identity proof, fuses (noisy-OR), updates the agent's risk and level (L3+ is sticky until a human releases).
3. The verdict is chosen *per action*: ALLOW, STEP_UP, DENY, or SANDBOX (route to the decoy). Shadow mode records `SHADOW:…` and enforces nothing.
4. Level changes re-issue the token via RFC 8693 exchange (scope can only shrink) or revoke it at L4.
5. The event is saved, appended to the audit chain, and broadcast on `/ws`; incidents are opened/updated as alerts with a causal chain, plane contributions and a narrative.

## API
`/ws` live stream · `/api/state` · `/api/agents[/{id}]` (+`/release`, `/isolate`) · `/api/events` · `/api/alerts[/{id}]` · `/api/timeline` ·
`/api/contracts[/{id}]` (+`/whatif`, `/suggest`, PUT to sign a new version) · `/api/scenarios`, `/api/attack`, `/api/playground`, `/api/runs` ·
`/api/sandbox` · `/api/tokens/{agent}`, `/api/token/exchange`, `/api/jwks` · `/api/audit`, `/verify`, `/tamper`, `/reseal` ·
`/api/delegation` · `/api/benchmarks` · `/api/mode`, `/api/sim`, `/api/reset`. Interactive docs at `http://localhost:8000/docs`.

## Additions in v1.1
* **Human step-up queue** (`Engine.pending`, `/api/approvals`): L1 holds sink actions with risk ≥ 30; a human approves or denies; both go to the audit chain.
* **Canary tripwire** (`Engine.confirm_canary`, `/api/canary/check`): every sandbox response embeds a unique canary; seeing one elsewhere raises a `confirmed` event (the only way besides an operator to reach L4).
* **Cold-start agents** (`Engine.spawn`, `POST /api/agents`): a new agent borrows its role's peer baseline (`adopt_peer_prior`) and is protected by the contract, decoys and provenance from call one.
* **Red-team autopilot** (`Hub.autopilot_loop`) cycles the scenario catalogue and auto-releases old quarantines.
* **Coverage / SIEM / reports**: `/api/coverage`, `/api/siem/cef`, `/api/alerts/{id}/report`, `/api/events/{id}`.
* **Metrics** (`/api/metrics`): engine and pipeline latency percentiles, throughput, DB flush time and queue depth, memory.
