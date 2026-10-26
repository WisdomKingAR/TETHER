# TETHER backend

FastAPI gateway and detection engine. See the [root README](../README.md) for the overview and [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the module map.

```bash
pip install -r requirements-dev.txt
python -m pytest                                  # 32 tests: engine + HTTP/WebSocket API
uvicorn driftward.main:app --reload --port 8000   # http://localhost:8000/docs
```

Configuration is by environment variables (see `.env.example`): `PORT`, `LOG_LEVEL`, `CORS_ORIGINS`, `TETHER_API_KEY`, `TETHER_AUTOPILOT`, `TETHER_DB`.

Design notes
- `core/` is pure domain logic (no I/O): planes, fusion, containment, tokens, scenarios.
- `services/hub.py` runs the event pipeline (score → persist → audit → broadcast) and the simulated traffic; `services/store.py` batches writes and keeps the audit hash chain in order.
- Every request gets an `X-Request-ID` and `X-Process-Time`; mutating or slow requests are logged. On shutdown the write queue is flushed.
