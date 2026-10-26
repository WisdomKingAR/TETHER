import React, { useEffect, useState } from "react";
import { Panel, LineChart, CountUp } from "../components/ui.jsx";
import { api } from "../api.js";

function Bars({ rows }) {
  return (
    <div className="grid" style={{ gap: 10 }}>
      <div className="row tiny dim" style={{ gap: 16 }}><span><b style={{ color: "#8a8a8a" }}>■</b> token + scope</span><span><b style={{ color: "#4d7fc0" }}>■</b> ML-only UEBA</span><span><b style={{ color: "#ff3b3b" }}>■</b> TETHER</span></div>
      {rows.map((r) => (
        <div key={r.name}>
          <div className="tiny" style={{ marginBottom: 3 }}>{r.name}</div>
          {[[0, "#8a8a8a"], [r.ml, "#4d7fc0"], [r.dw, "#ff3b3b"]].map(([v, c], i) => <div key={i} className="row" style={{ gap: 8, marginBottom: 2 }}><div className="riskbar" style={{ flex: 1, height: 9 }}><i style={{ width: v * 100 + "%", background: c, boxShadow: `0 0 10px ${c}` }} /></div><span className="mono tiny" style={{ width: 38, textAlign: "right" }}>{Math.round(v * 100)}%</span></div>)}
        </div>
      ))}
    </div>
  );
}

export default function Benchmarks() {
  const [b, setB] = useState(null); useEffect(() => { api.get("/api/benchmarks").then(setB); }, []);
  if (!b) return <div className="page"><p className="dim">loading…</p></div>;
  const rows = [["Prompt injection", b.scen.A1.ml, b.scen.A1.dw], ["Tool poisoning", b.scen.A2.ml, b.scen.A2.dw], ["Token replay", b.scen.A3.ml, b.scen.A3.dw], ["Slow drift", b.drift.ml.rate, b.drift.dw.rate], ["Mimicry", b.scen.A5.ml, b.scen.A5.dw], ["Sub-agent hijack", b.scen.A6.ml, b.scen.A6.dw]].map(([name, ml, dw]) => ({ name, ml, dw }));
  const ex = b.drift.example;
  const total = b.latency.total[0];
  return (
    <div className="page">
      <h1 className="h1">Benchmarks</h1><p className="sub">Results of the research simulation that tuned the engine: synthetic agent traces, 160 attacks per scenario, every system thresholded at a 1% false-alarm budget. {b.note} These are not claims about production; they are the bar the live prototype has to meet on real traces.</p>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: 14 }}>
        {[[b.fpr.dw * 100, "% false alarms", 2, "var(--green)"], [b.roc.dw.auc, "AUC (ML-only " + b.roc.ml.auc.toFixed(2) + ")", 2, "#fff"], [total, "µs core decision, p50", 1, "var(--cyan)"], [b.cold.dw[1] * 100, "% detected at 3 sessions of history", 0, "var(--red2)"]].map(([n, l, d, c]) => <Panel key={l}><div className="stat"><b style={{ color: c }}><CountUp to={n} decimals={d} /></b><span>{l}</span></div></Panel>)}
      </div>
      <div className="two" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Panel title="Detection rate by scenario" tag="at 1% FPR" glow><Bars rows={rows} /></Panel>
        <div className="grid" style={{ alignContent: "start" }}>
          <Panel title="Cold start: sessions of history vs detection"><LineChart w={520} h={190} bands={false} series={[{ name: "ml", data: b.cold.ml.map((x) => x * 100), color: "#4d7fc0", dots: true }, { name: "tether", data: b.cold.dw.map((x) => x * 100), color: "#ff3b3b", bold: true, dots: true }]} xs={b.cold.n} xLabel="sessions" /></Panel>
          <Panel title="Slow drift: CUSUM catches the creeping agent"><LineChart w={520} h={190} bands={false} yMax={Math.max(...ex.S, ex.h) * 1.1} series={[{ name: "creep", data: ex.S, color: "#ff3b3b", bold: true }, { name: "healthy", data: ex.ben_S, color: "#6cc58a" }, { name: "h", data: ex.S.map(() => ex.h), color: "#fff", dash: "4 4" }]} marks={ex.alarm != null ? [{ i: ex.alarm, label: "alarm", color: "#e8c34a" }] : []} xLabel="session" /></Panel>
        </div>
        <Panel title="ROC, pooled attacks"><LineChart w={520} h={220} bands={false} yMax={1} series={[{ name: "ml", data: b.roc.ml.tpr, color: "#4d7fc0" }, { name: "tether", data: b.roc.dw.tpr, color: "#ff3b3b", bold: true }]} xLabel="false-positive rate →" /></Panel>
        <Panel title="Inline decision path, measured"><div className="grid" style={{ gap: 7 }}>{Object.entries(b.latency).filter(([k]) => !k.startsWith("_") && k !== "total").map(([k, v]) => <div key={k}><div className="row tiny" style={{ justifyContent: "space-between" }}><span>{k}</span><span className="mono">{v[0].toFixed(2)} µs</span></div><div className="riskbar"><i style={{ width: Math.min(100, (v[0] / total) * 100) + "%", background: "#ff3b3b" }} /></div></div>)}<div className="tiny dim">pure Python, one core, no network. Async IsolationForest scoring {b.latency._async_if_ms[0].toFixed(1)} ms per session.</div></div></Panel>
      </div>
    </div>
  );
}
