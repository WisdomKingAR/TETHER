import React, { useEffect, useState } from "react";
import { Panel, CountUp } from "../components/ui.jsx";
import { API, api, PLANE_COLOR } from "../api.js";

export default function Coverage() {
  const [c, setC] = useState(null); const [cef, setCef] = useState("");
  useEffect(() => { const f = () => { api.get("/api/coverage").then(setC); fetch(API + "/api/siem/cef?limit=30").then((r) => r.text()).then(setCef); }; f(); const t = setInterval(f, 2500); return () => clearInterval(t); }, []);
  if (!c) return <div className="page"><p className="dim">loading…</p></div>;
  const max = Math.max(1, ...c.owasp.map((o) => o.hits));
  return (
    <div className="page">
      <h1 className="h1">Coverage & SIEM</h1>
      <p className="sub">Each OWASP Agentic Top 10 risk is tied to the evidence planes that detect it, with a live hit count from this session. The same events stream out in CEF so a SOC can ingest them into Splunk or Elastic unchanged.</p>
      <div className="grid" style={{ gridTemplateColumns: "repeat(7, 1fr)", marginBottom: 14 }}>
        {Object.entries(c.planes).map(([k, v]) => <Panel key={k}><div className="stat"><b style={{ color: PLANE_COLOR[k] }}><CountUp to={v.hits} dur={600} /></b><span>{v.label}</span></div></Panel>)}
      </div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.2fr) minmax(0,1fr)" }}>
        <Panel title="OWASP Agentic Top 10 (2026)" glow>
          <div className="grid" style={{ gap: 9 }}>
            {c.owasp.map((o) => (
              <div key={o.id} className="row" style={{ gap: 12 }}>
                <span className="mono" style={{ width: 52, color: "var(--red2)" }}>{o.id}</span>
                <div style={{ flex: 1 }}>
                  <div className="row" style={{ justifyContent: "space-between" }}><span style={{ fontSize: 13.5 }}>{o.name}</span><span className="tagrow">{o.planes.map((p) => <span key={p} className="chip" style={{ color: PLANE_COLOR[p], borderColor: PLANE_COLOR[p] }}>{p.toUpperCase()}</span>)}</span></div>
                  <div className="riskbar" style={{ height: 7, marginTop: 4 }}><i style={{ width: Math.max(4, (o.hits / max) * 100) + "%", background: o.hits ? "#ff3b3b" : "#3a2a2f", boxShadow: o.hits ? "0 0 12px #ff3b3b" : "none" }} /></div>
                </div>
                <span className="mono" style={{ width: 34, textAlign: "right" }}>{o.hits}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="SIEM stream · CEF" tag="GET /api/siem/cef">
          <pre className="mono" style={{ margin: 0, fontSize: 10.5, lineHeight: 1.55, color: "#9fdcff", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 520, overflowY: "auto" }}>{cef || "waiting for events…"}</pre>
        </Panel>
      </div>
    </div>
  );
}
