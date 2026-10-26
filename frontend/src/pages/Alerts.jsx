import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Panel, PlaneBars, Radial, LevelBadge, LineChart } from "../components/ui.jsx";
import { useStore } from "../store.js";
import { API, api, clock, fmtBytes, verdictClass, PLANE_COLOR, PLANE_LABEL, OWASP } from "../api.js";

function TokenDiff({ t }) {
  if (!t || (!t.before?.sub && !t.after?.sub)) return null;
  const row = (k, a, b) => <tr key={k}><td className="dim">{k}</td><td className="mono">{a ?? "—"}</td><td className="mono" style={{ color: String(a) !== String(b) ? "var(--amber)" : "inherit" }}>{b ?? "—"}</td></tr>;
  return (
    <table className="t"><thead><tr><th /><th>before</th><th>after (RFC 8693)</th></tr></thead><tbody>
      {row("level", t.before.lvl, t.after.lvl)}{row("ttl", t.before.ttl && t.before.ttl + "s", t.after.ttl && t.after.ttl + "s")}
      {row("scopes", (t.before.scope || []).length, (t.after.scope || []).length)}{row("actor", t.before.act || "—", t.after.act ? "gateway" : "—")}
      <tr><td className="dim">dropped</td><td colSpan="2" className="mono tiny" style={{ color: "var(--red2)" }}>{(t.before.scope || []).filter((x) => !(t.after.scope || []).includes(x)).join(", ") || "—"}</td></tr>
    </tbody></table>
  );
}

function Detail({ al }) {
  const [step, setStep] = useState(al.chain.length ? al.chain.length - 1 : 0); const [play, setPlay] = useState(false); const timer = useRef();
  useEffect(() => { setStep(Math.max(0, al.chain.length - 1)); setPlay(false); }, [al.id]);
  useEffect(() => {
    if (!play) return; setStep(0);
    let i = 0; timer.current = setInterval(() => { i++; if (i >= al.chain.length) { clearInterval(timer.current); setPlay(false); } else setStep(i); }, 900);
    return () => clearInterval(timer.current);
  }, [play]);
  const cur = al.chain[Math.min(step, al.chain.length - 1)];
  const standards = useMemo(() => [...new Set(Object.entries(al.planes).filter(([, v]) => v > 0).flatMap(([k]) => OWASP[k] || []))], [al]);
  const chart = al.chain.map((c) => c.risk);
  return (
    <div className="grid">
      <Panel glow className={al.status === "open" ? "alert-pulse" : ""} title={`${al.id} · ${al.display}`} tag={al.status}>
        <div className="row" style={{ alignItems: "flex-start", gap: 20 }}>
          <Radial value={al.peak} size={150} label="PEAK" />
          <div style={{ flex: 1 }}>
            <div className="row" style={{ gap: 8, marginBottom: 10 }}><LevelBadge level={al.level} /><span className={`chip ${al.mode === "enforce" ? "bad" : "shadow"}`}>{al.mode}</span><span className="chip">{al.chain.length} correlated events</span><span className="chip" style={{ color: al.leaked ? "var(--red)" : "var(--green)" }}>leaked {fmtBytes(al.leaked)}</span></div>
            <p style={{ margin: "0 0 10px", lineHeight: 1.65, fontSize: 15 }}>{al.narrative}</p>
            <div className="tiny dim">Action taken: <b style={{ color: "#fff" }}>{al.action}</b></div>
            <div className="tagrow" style={{ marginTop: 10 }}>{standards.map((s) => <span key={s} className="chip">{s}</span>)}</div>
          </div>
        </div>
        <div className="row" style={{ marginTop: 12, gap: 8 }}><button className="btn sm" onClick={() => api.post(`/api/agents/${al.agent}/release`)}>Release agent</button><button className="btn sm ghost" onClick={() => api.post(`/api/agents/${al.agent}/isolate`)}>Isolate (Tier 4)</button><Link to="/upside-down" className="btn sm ghost">View sandbox</Link><button className="btn sm ghost" onClick={async () => { const t = await fetch(API + `/api/alerts/${al.id}/report`).then((r) => r.text()); const u = URL.createObjectURL(new Blob([t], { type: "text/markdown" })); const l = document.createElement("a"); l.href = u; l.download = `${al.id}-incident-report.md`; l.click(); }}>⬇ Incident report</button></div>
      </Panel>
      <div className="two">
        <Panel title="Why: evidence by plane"><PlaneBars planes={al.planes} labels={PLANE_LABEL} colors={PLANE_COLOR} />
          <div style={{ marginTop: 14 }}>{al.reasons.map((r, i) => <div key={i} className="tiny" style={{ padding: "4px 0", borderBottom: "1px solid var(--line2)" }}>• {r}</div>)}</div></Panel>
        <Panel title="Token before → after"><TokenDiff t={al.tokens} /><div className="tiny dim" style={{ marginTop: 8 }}>The token stayed cryptographically valid throughout. Containment narrowed it by exchange (scope can only shrink) instead of blocking the whole agent.</div></Panel>
      </div>
      <Panel title="Causal chain · time machine" tag={cur ? `step ${Math.min(step, al.chain.length - 1) + 1} / ${al.chain.length}` : ""}>
        <div className="row" style={{ marginBottom: 10, gap: 10 }}>
          <button className="btn sm primary" onClick={() => setPlay(true)} disabled={play || !al.chain.length}>{play ? "replaying…" : "▶ Replay incident"}</button>
          <input type="range" min="0" max={Math.max(0, al.chain.length - 1)} value={Math.min(step, Math.max(0, al.chain.length - 1))} onChange={(e) => { setPlay(false); setStep(+e.target.value); }} style={{ flex: 1 }} />
        </div>
        <div className="two" style={{ gridTemplateColumns: "1.3fr 1fr" }}>
          <div className="tl">
            {al.chain.map((c, i) => (
              <div key={c.id + "-" + i} className={`tli ${c.risk >= 60 ? "risky" : ""} ${i === step ? "cur" : ""}`} style={{ "--dot": c.risk >= 60 ? "#ff3b3b" : c.risk >= 30 ? "#e8c34a" : "#6cc58a", opacity: i <= step ? 1 : 0.35 }} onClick={() => { setPlay(false); setStep(i); }}>
                <div className="row" style={{ gap: 8 }}><span className="mono tiny dim">{clock(c.ts)}</span><b className="mono" style={{ fontSize: 13 }}>{c.tool}</b><span className="dim mono tiny" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 190 }}>{c.target}</span><span className="spacer" /><span className="chip ok">IAM ALLOW</span><span className={`chip ${verdictClass(c.verdict)}`}>{c.verdict}</span></div>
              </div>
            ))}
          </div>
          <div className="grid" style={{ alignContent: "start" }}>
            <LineChart w={380} h={150} series={[{ name: "Drift Score D", data: chart.map((v, i) => (i <= step ? v : null)), color: "#ff3b3b", bold: true, dots: true }]} bands />
            {cur && <div><div className="ptitle" style={{ fontSize: 11 }}>Evidence at this step</div>
              {Object.entries(cur.planes).length === 0 && <div className="dim tiny">no plane fired (context event)</div>}
              {Object.entries(cur.planes).map(([k, v]) => <div key={k} style={{ margin: "6px 0" }}><span className="chip" style={{ color: PLANE_COLOR[k], borderColor: PLANE_COLOR[k] }}>{PLANE_LABEL[k]}</span>{v.reasons.map((r, i) => <div key={i} className="tiny" style={{ marginTop: 3, paddingLeft: 4 }}>{r}</div>)}</div>)}</div>}
          </div>
        </div>
      </Panel>
    </div>
  );
}

export default function Alerts() {
  const s = useStore(); const { id } = useParams(); const nav = useNavigate(); const [base, setBase] = useState({});
  useEffect(() => { api.get("/api/alerts").then((l) => { const o = {}; l.forEach((a) => (o[a.id] = a)); setBase(o); }); }, []);
  const all = { ...base, ...s.alerts }; const list = Object.values(all).sort((a, b) => b.opened - a.opened);
  const al = all[id] || (id ? null : list[0]);
  return (
    <div className="page">
      <h1 className="h1">Alerts</h1><p className="sub">One alert per incident: a Composite Drift Score (D), the causal chain, the plane-by-plane evidence, the token change and the response taken. Replay any incident step by step.</p>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,0.55fr) minmax(0,1.9fr)" }}>
        <div className="grid" style={{ alignContent: "start" }}>
          {list.length === 0 && <Panel><div className="dim">No incidents yet. Launch one from the <Link to="/lab" style={{ color: "var(--red2)" }}>Attack Lab</Link>.</div></Panel>}
          {list.map((a) => (
            <Panel key={a.id} className={`acard ${al?.id === a.id ? "sel" : ""}`} style={{ "--c": a.status === "open" ? "#ff3b3b" : "#6cc58a" }} onClick={() => nav(`/alerts/${a.id}`)}>
              <div className="row" style={{ justifyContent: "space-between" }}><b className="mono">{a.id}</b><span className={`chip ${a.status === "open" ? "bad" : "ok"}`}>{a.status}</span></div>
              <div style={{ fontSize: 13, margin: "4px 0" }}>{a.display}</div>
              <div className="row tiny dim" style={{ justifyContent: "space-between" }}><span>Peak D <b style={{ color: "#fff" }}>{Math.round(a.peak)}</b></span><span>{a.level_name}</span><span>{a.chain.length} ev</span></div>
            </Panel>
          ))}
        </div>
        {al ? <Detail al={al} key={al.id} /> : <Panel><div className="dim">Select an alert.</div></Panel>}
      </div>
    </div>
  );
}
