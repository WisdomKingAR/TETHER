"""Event hub: runs the detection engine, persists, audits and broadcasts. Also drives benign traffic and attack runs."""
from __future__ import annotations
import asyncio, collections, json, random, time, uuid
import os
try:
    import resource
except ImportError:
    resource = None
import numpy as np
from fastapi import WebSocket
from . import store
from ..core import scenarios
from ..core.engine import Engine, LEVELS
from ..core.roles import AGENT_ORDER


def compact(out: dict) -> dict:
    ev = out["event"]
    return dict(type="event", id=ev["id"], ts=ev["ts"], agent=ev["agent"], tool=ev["tool"], target=ev.get("target") or ev.get("egress", ""), bytes=int(ev.get("bytes", 0)),
                sink=bool(ev.get("sink")), taint=bool(ev.get("taint")), run_id=ev.get("run_id"), label=ev.get("label"), attacker=ev.get("attacker", False), note=ev.get("note"),
                risk=out["risk"], agent_risk=out["agent_risk"], verdict=out["verdict"], level=out["level"], level_name=out["level_name"], leaked=out["leaked"], escalated=out["escalated"], risky=out["risky"],
                planes={k: dict(score=v["score"], contrib=v["contrib"], reasons=v["reasons"]) for k, v in out["planes"].items()}, agent_state=out["agent_state"], iam=out["iam"], ramp=ev.get("ramp"))


class Hub:
    def __init__(self):
        store.init(fresh=True)
        self.engine = Engine()
        self.clients: set[WebSocket] = set()
        self.sse_clients: set = set()   # asyncio.Queue per SSE subscriber
        self.paused = False
        self.speed = 1.0
        self.runs: dict[str, dict] = {}
        self.tasks: list[asyncio.Task] = []
        self.loops: dict[str, asyncio.Task] = {}
        self.rng = random.Random(3)
        self.cursor = {r: None for r in AGENT_ORDER}
        self.history_tail: list[dict] = []   # compact events for late joiners
        self.nrng = np.random.default_rng(7)
        self.lat = collections.deque(maxlen=4000)      # engine.process latency, seconds
        self.lat_emit = collections.deque(maxlen=4000)  # full emit latency
        self.stamps = collections.deque(maxlen=4000)
        self.t0 = time.time()
        self.total = 0
        self.autopilot = False
        self.autopilot_interval = 14.0
        self.autopilot_log: list[dict] = []

    # ------------------------------------------------------------------ websocket
    async def connect(self, ws: WebSocket):
        await ws.accept(); self.clients.add(ws)
        await ws.send_text(json.dumps(dict(type="hello", autopilot=self.autopilot, pending=list(self.engine.pending.values()), snapshot=self.engine.snapshot(), tail=self.history_tail[-120:], runs=list(self.runs.values())[-5:])))

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def broadcast(self, msg: dict):
        data = json.dumps(msg, default=str)
        dead = []
        for c in list(self.clients):
            try: await c.send_text(data)
            except Exception: dead.append(c)  # noqa: BLE001
        for c in dead: self.clients.discard(c)
        # SSE fan-out
        dead_q = []
        for q in list(self.sse_clients):
            try:
                q.put_nowait(msg)
            except Exception:
                dead_q.append(q)
        for q in dead_q:
            self.sse_clients.discard(q)

    # ------------------------------------------------------------------ ingest
    async def emit(self, ev: dict) -> dict:
        had = set(self.engine.alerts)
        t0 = time.perf_counter()
        out = self.engine.process(ev)
        t1 = time.perf_counter()
        msg = compact(out)
        store.save_event(out)
        rec = store.audit_append(dict(event=msg["id"], agent=msg["agent"], tool=msg["tool"], target=msg["target"], risk=msg["risk"], verdict=msg["verdict"], level=msg["level_name"], contract=out["agent_state"]["contract_version"]))
        msg["audit_hash"] = rec["hash"][:12]
        self.history_tail.append(msg); self.history_tail = self.history_tail[-400:]
        await self.broadcast(msg)
        t2 = time.perf_counter(); self.lat.append(t1 - t0); self.lat_emit.append(t2 - t0); self.stamps.append(time.time()); self.total += 1
        a = self.engine.agents[ev["agent"]]
        if a.incident or set(self.engine.alerts) - had:
            al = self.engine.alerts.get(a.incident) if a.incident else None
            if al is None:  # alert just closed this tick
                al = max(self.engine.alerts.values(), key=lambda x: x["opened"], default=None)
            if al:
                store.save_alert(al)
                await self.broadcast(dict(type="alert", alert=al, new=al["id"] not in had))
        return msg

    # ------------------------------------------------------------------ benign traffic
    def benign_event(self, role: str) -> dict:
        a = self.engine.agents[role]; k = len(a.tools)
        cur = self.cursor[role]
        cur = self.rng.randrange(k) if cur is None else int(self.nrng.choice(k, p=a.T[cur]))
        self.cursor[role] = cur
        name, cls, mean_b, sink, ingest = a.meta[a.tools[cur]]
        ev = dict(agent=role, tool=name, data_class=cls, sink=bool(sink), bytes=float(self.nrng.lognormal(np.log(mean_b), 0.35)), hour=int(np.clip(self.rng.gauss(13, 2.5), 6, 22)))
        if sink:
            pat = self.rng.choice(a.contract["egress"]); ev["egress"] = pat.replace("*", "mail")
        if ingest: ev["target"] = f"{self.rng.choice(['quote', 'invoice', 'brief', 'spec'])}_{self.rng.randrange(100, 999)}.pdf"
        if self.rng.random() < 0.012: ev["host_novel"] = True
        return ev

    async def benign_loop(self, role: str):
        await asyncio.sleep(self.rng.uniform(0.2, 1.4))
        while True:
            try:
                if not self.paused and self.engine.agents[role].level < 4:
                    await self.emit(self.benign_event(role))
            except KeyError:
                return          # agent was removed
            except Exception as e:  # noqa: BLE001
                print("benign loop error", role, e)
            await asyncio.sleep(self.rng.uniform(2.5, 4.0) / max(self.speed, 0.1))

    async def autopilot_loop(self):
        """Red-team autopilot: periodically launches a random attack and releases agents once they have been caged for a while."""
        order = [s["id"] for s in scenarios.CATALOG]
        i = 0
        while True:
            await asyncio.sleep(1.0)
            if not self.autopilot or self.paused:
                continue
            now = time.time()
            for r, a in self.engine.agents.items():       # auto-release old quarantines so the show goes on
                if a.level >= 3 and not a.incident is None and now - self.engine.alerts[a.incident]["opened"] > 26 and not any(x["status"] == "running" and x["agent"] == r for x in self.runs.values()):
                    self.engine.release(r); await self.broadcast(dict(type="agent", agent=a.public()))
            if any(x["status"] == "running" for x in self.runs.values()):
                continue
            sid = order[i % len(order)]; i += 1
            if sid == "slow_drift" and i % 2: sid = order[(i + 1) % len(order)]
            meta = scenarios.BY_ID[sid]
            if self.engine.agents[meta["agent"]].level >= 3:
                continue
            run = await self.start_run(sid, None)
            self.autopilot_log = ([dict(ts=now, scenario=sid, run=run["id"])] + self.autopilot_log)[:20]
            await self.broadcast(dict(type="autopilot_fired", scenario=sid, run=run["id"], title=run["title"]))
            await asyncio.sleep(self.autopilot_interval)

    async def flush_loop(self):
        while True:
            await asyncio.sleep(0.4)
            if store.pending():
                await asyncio.to_thread(store.flush)

    def metrics(self) -> dict:
        def pct(d, q):
            if not d: return 0.0
            s = sorted(d); return s[min(len(s) - 1, int(len(s) * q))] * 1e6
        now = time.time(); recent = sum(1 for t in self.stamps if now - t <= 10)
        mem = 0.0
        if resource:
            try:
                is_darwin = hasattr(os, "uname") and os.uname().sysname == "Darwin"
                mem = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if is_darwin else 1024), 1)
            except Exception:
                mem = 0.0
        return dict(uptime_s=int(now - self.t0), events_total=self.total, events_per_s=round(recent / 10, 1), engine_us=dict(p50=round(pct(self.lat, .5), 1), p95=round(pct(self.lat, .95), 1), p99=round(pct(self.lat, .99), 1)),
                    pipeline_us=dict(p50=round(pct(self.lat_emit, .5), 1), p95=round(pct(self.lat_emit, .95), 1)), db_queue=store.pending(), db=store.stats, ws_clients=len(self.clients),
                    agents=len(self.engine.agents), memory_mb=mem)

    def start(self):
        self.loops = {r: asyncio.create_task(self.benign_loop(r)) for r in AGENT_ORDER}
        self.tasks = list(self.loops.values()) + [asyncio.create_task(self.autopilot_loop()), asyncio.create_task(self.flush_loop())]

    # ------------------------------------------------------------------ attack runs
    async def run_steps(self, run: dict, steps: list[dict], agent: str, sync: bool = False):
        run_id = run["id"]
        await self.broadcast(dict(type="run_start", run=run, steps=run.get("steps", [])))
        first_flag = None; leaked = 0.0; would_leak = 0.0; max_risk = 0.0
        for i, s in enumerate(steps):
            ev = {k: v for k, v in s.items() if k not in ("delay",)}
            ev.setdefault("agent", agent); ev["run_id"] = run_id; ev["step"] = i
            msg = await self.emit(ev)
            max_risk = max(max_risk, msg["risk"]); leaked += msg["leaked"]
            if s.get("sink") and s.get("attacker", True): would_leak += s.get("bytes", 0)
            if first_flag is None and msg["risky"] and s.get("attacker", True): first_flag = i
            step_result = dict(type="run_step", run_id=run_id, i=i, label=s["label"], risk=msg["risk"], agent_risk=msg["agent_risk"], verdict=msg["verdict"], level=msg["level"], event_id=msg["id"], leaked=msg["leaked"], attacker=s.get("attacker", True), note=s.get("note"), iam="ALLOW", quiet=s.get("quiet", False))
            run["results"].append(step_result)
            await self.broadcast(step_result)
            if not sync:
                await asyncio.sleep(s.get("delay", 1.0) / max(self.speed, 0.1))
        a = self.engine.agents[agent]
        alert = a.incident or next((k for k, v in reversed(list(self.engine.alerts.items())) if v["agent"] == agent), None)
        summary = dict(first_flagged_step=first_flag, leaked_bytes=int(leaked), iam_only_would_leak=int(would_leak), max_risk=max_risk, final_level=a.level, final_level_name=LEVELS[a.level], alert=alert, enforce=self.engine.enforce)
        run.update(summary=summary, status="done")
        await self.broadcast(dict(type="run_end", run_id=run_id, summary=summary))

    async def start_run(self, scenario: str, agent: str | None, steps: list[dict] | None = None, title: str | None = None, sync: bool = False) -> dict:
        meta = scenarios.BY_ID.get(scenario, dict(title=title or scenario, agent=agent))
        agent = agent or meta["agent"]
        steps = steps or scenarios.build(scenario, agent, self.engine)
        run_steps_info = [dict(i=i, label=s["label"], tool=s["tool"], attacker=s.get("attacker", True), quiet=s.get("quiet", False)) for i, s in enumerate(steps)]
        run = dict(id=uuid.uuid4().hex[:8], scenario=scenario, agent=agent, title=title or meta["title"], started=time.time(), status="running", n=len(steps), steps=run_steps_info, results=[])
        self.runs[run["id"]] = run
        if sync:
            await self.run_steps(run, steps, agent, sync=True)
        else:
            self.tasks.append(asyncio.create_task(self.run_steps(run, steps, agent)))
        return run

    async def spawn(self, template: str, name: str | None) -> dict:
        a = self.engine.spawn(template, name)
        self.cursor[a.role] = None
        self.loops[a.role] = asyncio.create_task(self.benign_loop(a.role))
        pub = a.public()
        await self.broadcast(dict(type="spawned", agent=pub, order=list(self.engine.agents)))
        return pub

    async def despawn(self, rid: str):
        t = self.loops.pop(rid, None)
        if t: t.cancel()
        self.engine.remove(rid); self.cursor.pop(rid, None)
        await self.broadcast(dict(type="removed", id=rid, order=list(self.engine.agents)))

    async def reset(self):
        for rid in [r for r, a in self.engine.agents.items() if a.spawned]:
            t = self.loops.pop(rid, None)
            if t: t.cancel()
        self.paused = True; await asyncio.sleep(0.3)
        store.init(fresh=True); self.engine.reset(); self.cursor = {r: None for r in self.engine.agents}; self.runs.clear(); self.history_tail.clear()
        await self.broadcast(dict(type="reset", snapshot=self.engine.snapshot()))
        self.paused = False
