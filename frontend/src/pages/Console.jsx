import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Constellation3D from "../components/Constellation3D.jsx";
import { Panel, Spark, LevelBadge, RiskBar, Radial, Heat, CountUp } from "../components/ui.jsx";
import { useStore, updateStore, syncState, recordEvent } from "../store.js";
import { api, LEVEL_COLORS, fmtBytes, clock, verdictClass, PLANE_LABEL, PLANE_COLOR } from "../api.js";

function AgentDetail({ id }) {
  const s = useStore(); const a = s.agents[id]; const [d, setD] = useState(null);
  useEffect(() => { api.get(`/api/agents/${id}`).then(setD).catch(() => {}); }, [id, a?.contract_version]);
  const [tok, setTok] = useState(null);
  useEffect(() => { api.get(`/api/tokens/${id}`).then(setTok).catch(() => {}); }, [id, a?.level, a?.contract_version]);
  if (!a) return null;
  const series = (s.series[id] || []).map((x) => x.risk);
  return (
    <Panel title={a.display} tag={`contract v${a.contract_version}`} glow>
      <div className="row" style={{ alignItems: "flex-start", gap: 18 }}>
        <Radial value={a.risk} size={140} />
        <div className="grid" style={{ gap: 8, flex: 1 }}>
          <div><LevelBadge level={a.level} /> {a.level === 2 && <span className="chip warn" style={{ marginLeft: 6 }}>Surgical Clip Active</span>}{a.taint && <span className="chip warn" style={{ marginLeft: 6 }}>T2 context</span>}{a.incident && <Link to={`/alerts/${a.incident}`} className="chip bad" style={{ marginLeft: 6 }}>{a.incident}</Link>}</div>
          <Spark data={series} w={280} h={54} color={LEVEL_COLORS[Math.max(a.level, 0)] === "#6cc58a" ? a.color : LEVEL_COLORS[a.level]} />
          <div className="row tiny dim" style={{ gap: 14 }}><span>events <b style={{ color: "#fff" }}>{a.stats.events}</b></span><span>flagged <b style={{ color: "#fff" }}>{a.stats.flagged}</b></span><span>sandboxed <b style={{ color: "var(--violet)" }}>{a.stats.sandboxed}</b></span><span>leaked <b style={{ color: a.stats.leaked ? "var(--red)" : "var(--green)" }}>{fmtBytes(a.stats.leaked)}</b></span></div>
          <div className="tiny dim">drift (CUSUM) <b style={{ color: "#fff" }}>{Math.round(a.cusum * 100)}%</b> of alarm</div><RiskBar value={a.cusum * 100} color="#6cc58a" />
        </div>
      </div>
      <div className="row" style={{ marginTop: 12, gap: 8 }}>
        <button className="btn sm" onClick={() => api.post(`/api/agents/${id}/release`)}>Release</button>
        <button className="btn sm ghost" onClick={() => api.post(`/api/agents/${id}/isolate`)}>Isolate (Tier 4)</button>
        <Link className="btn sm ghost" to="/contracts">Contract</Link>
      </div>
      {tok && (
        <div style={{ marginTop: 14 }}>
          <div className="ptitle" style={{ fontSize: 11 }}>Token</div>
          <div className="mono tiny" style={{ lineHeight: 1.6 }}>
            <div>sub <span className="dim">spiffe://tether/agent/{id}</span></div>
            <div>lvl <b>{tok.current.lvl}</b> · ttl <b>{tok.current.ttl}s</b>{tok.current.act && <> · act <span style={{ color: "var(--violet)" }}>gateway</span></>}</div>
            <div>scope <span className="dim">{(tok.current.scope || []).join(" ")}</span></div>
            {tok.current.prev && <div style={{ color: "var(--amber)" }}>exchanged from {tok.current.prev} (RFC 8693)</div>}
          </div>
        </div>
      )}
      {d && <div style={{ marginTop: 12 }}><div className="ptitle" style={{ fontSize: 11 }}>Learned tool→tool behaviour</div><Heat m={d.transition} labels={d.tools.map((t) => t.name.split(".")[0])} size={26} /></div>}
    </Panel>
  );
}

function Inspector({ id, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.get(`/api/events/${id}`).then(setD).catch(() => setD({ error: true })); }, [id]);
  return (
    <div className="cmdk" onClick={onClose}><div style={{ width: "min(760px,94vw)", maxHeight: "80vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
      <div className="ptitle">Event inspector · #{id}<span className="tag"><button className="btn ghost sm" onClick={onClose}>close</button></span></div>
      {!d && <div className="dim">loading…</div>}
      {d && !d.error && <>
        <div className="row" style={{ gap: 10, marginBottom: 10 }}><b className="mono">{d.event.agent} · {d.event.tool}</b><span className={`chip ${verdictClass(d.verdict)}`}>{d.verdict}</span><span className="chip" style={{ color: "var(--red)" }}>D = {Math.round(d.risk)}</span><span className="chip">{d.level_name}</span></div>
        {d.shapley && (
          <div style={{ marginBottom: 10, padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)" }}>
            <div className="ptitle" style={{ fontSize: 11, marginBottom: 6 }}>5-Factor Exact Shapley Attribution (2⁵ = 32 coalitions)</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {Object.entries(d.shapley).map(([k, val]) => (
                <span key={k} className="chip" style={{ borderColor: PLANE_COLOR[k] || "var(--mute)" }}>
                  <span style={{ color: PLANE_COLOR[k] || "var(--accent)" }}>{k}</span>: <b>+{val}</b>
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 8 }}>
          {Object.entries(d.planes).map(([k, v]) => <div key={k} className="panel" style={{ padding: 10, opacity: v.score > 0 ? 1 : 0.45 }}><div className="row" style={{ justifyContent: "space-between" }}><b style={{ color: PLANE_COLOR[k], fontSize: 12 }}>{PLANE_LABEL[k]}</b><span className="mono tiny">{v.score.toFixed(2)}</span></div><RiskBar value={v.score * 100} color={PLANE_COLOR[k]} />{v.reasons.map((r, i) => <div key={i} className="tiny" style={{ marginTop: 4 }}>{r}</div>)}</div>)}
        </div>
        <pre className="mono tiny" style={{ marginTop: 12, padding: 10, background: "rgba(0,0,0,.5)", borderRadius: 8, color: "#9fdcff", whiteSpace: "pre-wrap" }}>{JSON.stringify(d.event, null, 1)}</pre>
      </>}
    </div></div>
  );
}

function Metrics() {
  const [m, setM] = useState(null);
  useEffect(() => { const f = () => api.get("/api/metrics").then(setM).catch(() => {}); f(); const t = setInterval(f, 2000); return () => clearInterval(t); }, []);
  if (!m) return null;
  return (
    <div className="row tiny mono dim" style={{ gap: 18, flexWrap: "wrap", margin: "-4px 0 12px" }}>
      <span>gateway engine <b style={{ color: "var(--green)" }}>{m.engine_us.p50} µs</b> p50 · {m.engine_us.p99} µs p99</span>
      <span>pipeline <b style={{ color: "#fff" }}>{m.pipeline_us.p50} µs</b></span><span>throughput <b style={{ color: "#fff" }}>{m.events_per_s}/s</b></span>
      <span>db batch <b style={{ color: "#fff" }}>{m.db.last_flush_ms} ms</b> · queue {m.db_queue}</span><span>ws clients {m.ws_clients}</span><span>mem {m.memory_mb} MB</span><span>uptime {m.uptime_s}s</span>
    </div>
  );
}

function Spawner({ s, onPick }) {
  const [t, setT] = useState("procurement"); const [busy, setBusy] = useState(false);
  const base = s.order.filter((id) => !s.agents[id]?.spawned && !id.includes("-x"));
  const spawn = async () => { setBusy(true); try { const a = await api.post("/api/agents", { template: t }); onPick(a.id); } finally { setBusy(false); } };
  const extras = s.order.filter((id) => s.agents[id]?.spawned);
  return (
    <Panel title="Spawn a brand-new agent" tag="cold start · no history">
      <div className="dim tiny" style={{ marginBottom: 8, lineHeight: 1.55 }}>A fresh agent has zero history. It is protected from its first call by its signed contract, decoys, provenance and the peer-group prior of its role. Spawn one, then attack it from the Attack Lab.</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <select value={t} onChange={(e) => setT(e.target.value)}>{["procurement", "hr_help", "code_review", "finance_recon"].map((x) => <option key={x} value={x}>{s.agents[x]?.display || x}</option>)}</select>
        <button className="btn primary sm" disabled={busy} onClick={spawn}>＋ Spawn</button>
      </div>
      {extras.length > 0 && <div className="tagrow" style={{ marginTop: 10 }}>{extras.map((id) => <span key={id} className="edit-chip" style={{ cursor: "pointer" }} onClick={() => onPick(id)}>{s.agents[id].display}<button onClick={(e) => { e.stopPropagation(); api.del(`/api/agents/${id}`); }}>×</button></span>)}</div>}
    </Panel>
  );
}

function FleetHeat({ s }) {
  return (
    <Panel title="Fleet heat" tag="last 60 events per agent">
      <div className="grid" style={{ gap: 5 }}>
        {s.order.map((id) => { const ser = (s.series[id] || []).slice(-60); return (
          <div key={id} className="row" style={{ gap: 8 }}><span className="mono tiny dim" style={{ width: 92 }}>{id}</span>
            <div style={{ display: "flex", gap: 1.5, flex: 1 }}>{Array.from({ length: 60 }).map((_, i) => { const p = ser[i - (60 - ser.length)]; const v = p ? p.risk : -1; return <i key={i} style={{ flex: 1, height: 14, borderRadius: 2, background: v < 0 ? "rgba(255,255,255,.04)" : v >= 85 ? "#ff3b3b" : v >= 60 ? "#f08a3c" : v >= 30 ? "#e8c34a" : "#2f6b4a", boxShadow: v >= 85 ? "0 0 8px #ff3b3b" : "none" }} />; })}</div>
          </div>); })}
      </div>
    </Panel>
  );
}

export default function Console() {
  const s = useStore(); const [sel, setSel] = useState("procurement"); const [insp, setInsp] = useState(null);
  const list = s.order.map((id) => s.agents[id]).filter(Boolean);

  useEffect(() => {
    api.get("/api/state").then(syncState).catch(() => {});
    const timer = setInterval(async () => {
      try {
        const st = await api.get("/api/state");
        if (st) syncState(st);
        if (!s.connected && !s.paused) {
          const tickRes = await api.post("/api/tick");
          if (tickRes && tickRes.event) recordEvent(tickRes.event);
        }
      } catch (_) {}
    }, 4500);
    return () => clearInterval(timer);
  }, [s.connected, s.paused]);

  const setMode = async (enforce) => {
    updateStore({ mode: enforce ? "enforce" : "shadow" });
    try { await api.post("/api/mode", { enforce }); } catch (e) { console.error(e); }
  };
  const togglePause = async () => {
    const next = !s.paused;
    updateStore({ paused: next });
    try { await api.post("/api/sim", { paused: next }); } catch (e) { console.error(e); }
  };
  const cycleSpeed = async () => {
    const next = s.speed >= 4 ? 1 : s.speed * 2;
    updateStore({ speed: next });
    try { await api.post("/api/sim", { speed: next }); } catch (e) { console.error(e); }
  };
  const toggleAutopilot = async () => {
    const next = !s.autopilot;
    updateStore({ autopilot: next });
    try {
      const res = await api.post("/api/autopilot", { on: next });
      if (res && typeof res.on === "boolean") updateStore({ autopilot: res.on });
    } catch (e) {
      updateStore({ autopilot: !next });
      console.error("Autopilot toggle failed", e);
    }
  };
  return (
    <div className="page">
      <div className="row" style={{ alignItems: "flex-end", marginBottom: 14 }}>
        <div><h1 className="h1">Live Console</h1><p className="sub" style={{ margin: 0 }}>Five autonomous agents. Every tool call passes the gateway; each pulse you see is a real event scored by five drift factors.</p></div>
        <div className="spacer" />
        <div className="seg"><button className={s.mode === "shadow" ? "on" : ""} onClick={() => setMode(false)}>Shadow</button><button className={s.mode === "enforce" ? "on" : ""} onClick={() => setMode(true)}>Enforce</button></div>
        <div className="seg"><button onClick={togglePause}>{s.paused ? "▶ Resume" : "❚❚ Pause"}</button><button onClick={cycleSpeed}>{s.speed}×</button></div>
        <button className={`btn sm ${s.autopilot ? "primary" : "ghost"}`} onClick={toggleAutopilot}>☠ Red-team autopilot {s.autopilot ? "ON" : "off"}</button>
        <button className="btn ghost sm" onClick={() => api.post("/api/reset")}>Reset</button>
      </div>
      <Metrics />
      <div className="grid" style={{ gridTemplateColumns: "repeat(5, 1fr)", marginBottom: 14 }}>
        {[["Events inspected", s.counts.events, ""], ["Flagged", s.counts.flagged, "var(--amber)"], ["Sandboxed", s.counts.sandboxed, "var(--violet)"], ["Open alerts", Object.values(s.alerts).filter((a) => a.status === "open").length, "var(--red)"], ["Bytes leaked", s.counts.leaked, s.counts.leaked ? "var(--red)" : "var(--green)"]].map(([l, v, c]) => (
          <Panel key={l}><div className="stat"><b style={{ color: c || "#fff" }}>{l === "Bytes leaked" ? fmtBytes(v) : <CountUp to={v} dur={500} />}</b><span>{l}</span></div></Panel>
        ))}
      </div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)" }}>
        <div className="grid">
          <Panel title="Agent constellation" tag={s.connected ? "streaming" : "offline"} glow style={{ padding: 8 }}>
            <Constellation3D agents={s.agents} order={s.order} selected={sel} onSelect={setSel} pulses={s.pulses} height={470} />
          </Panel>
          <FleetHeat s={s} /><Spawner s={s} onPick={setSel} />
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            {list.map((a) => (
              <Panel key={a.id} className={`acard ${sel === a.id ? "sel" : ""} ${a.level >= 3 ? "alert-pulse" : ""}`} style={{ "--c": a.color }} onClick={() => setSel(a.id)}>
                <div className="row" style={{ justifyContent: "space-between" }}><b style={{ fontSize: 13 }}>{a.display}</b><LevelBadge level={a.level} /></div>
                <div style={{ margin: "8px 0 4px" }}><Spark data={(s.series[a.id] || []).map((x) => x.risk)} w={190} h={34} color={a.color} /></div>
                <div className="row tiny dim" style={{ justifyContent: "space-between" }}><span>D <b style={{ color: "#fff" }}>{Math.round(a.risk)}</b></span><span>v{a.contract_version}</span><span>{a.stats.events} ev</span></div>
              </Panel>
            ))}
          </div>
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <AgentDetail id={sel} />
          <Panel title="Live gateway feed" tag="agent · tool · risk · verdict">
            <div className="feed">
              {s.events.slice(0, 60).map((e) => (
                <div key={e.id} onClick={() => setInsp(e.id)} style={{ cursor: "pointer" }} className={`frow ${e.risky ? "risky" : ""} ${e.attacker ? "attacker" : ""}`} title={e.planes && Object.entries(e.planes).filter(([, v]) => v.score > 0).map(([k]) => PLANE_LABEL[k]).join(", ")}>
                  <span className="dim">{clock(e.ts)}</span><span style={{ color: s.agents[e.agent]?.color }}>{e.agent}</span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.tool} <span className="dim">{e.target}</span></span>
                  <span style={{ color: e.risk >= 85 ? "var(--red)" : e.risk >= 60 ? "var(--amber)" : "var(--mute)" }}>{Math.round(e.risk)}</span>
                  <span className={`chip ${verdictClass(e.verdict)}`}>{e.verdict}</span>
                </div>
              ))}
              {s.events.length === 0 && <div className="dim tiny mono">waiting for traffic…</div>}
            </div>
          </Panel>
        </div>
      </div>
      {insp && <Inspector id={insp} onClose={() => setInsp(null)} />}
    </div>
  );
}
