import React, { useEffect, useState } from "react";
import { toast } from "../store.js";
import UpsideScene from "../components/UpsideScene.jsx";
import { Panel } from "../components/ui.jsx";
import { useStore } from "../store.js";
import { api, clock, fmtBytes } from "../api.js";

export default function Upside() {
  const s = useStore(); const [data, setData] = useState({}); const [flip, setFlip] = useState(true); const [ready, setReady] = useState(false);
  useEffect(() => { const t = setTimeout(() => setReady(true), 1400); return () => clearTimeout(t); }, []);   // let the WebGL canvas size itself before the world flips
  const on = flip && ready;
  const live = s.events.filter((e) => e.verdict.includes("ISOLATE") || e.verdict.includes("SANDBOX")).length;
  useEffect(() => { const f = () => api.get("/api/sandbox").then(setData); f(); const t = setInterval(f, 2000); return () => clearInterval(t); }, []);
  const entries = Object.entries(data).flatMap(([agent, v]) => v.entries.map((e) => ({ ...e, agent, display: v.agent.display }))).sort((a, b) => b.ts - a.ts);
  const quarantined = Object.values(data).length;
  const [cv, setCv] = useState(""); const [cr, setCr] = useState(null); const [cans, setCans] = useState([]);
  useEffect(() => { const f = () => api.get("/api/canaries").then(setCans); f(); const t = setInterval(f, 2500); return () => clearInterval(t); }, []);
  const check = async () => { const r = await api.post("/api/canary/check", { value: cv }); setCr(r); if (r.found) toast({ title: "CANARY TRIPPED", body: `A decoy credential from ${r.agent} was used outside the sandbox. Exfiltration confirmed; agent isolated.`, to: "/alerts/" + r.alert }); };
  return (
    <div className="page">
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div><h1 className="h1">The Upside-Down</h1><p className="sub">When an agent enters ISOLATE (Tier 3), its risky calls are routed here: a decoy sandbox that answers with plausible fake data and canary credentials. The attacker believes it is winning. We record intent, tools and destination, and the agent's real work continues.</p></div>
        <div className="spacer" />
        <div className="seg"><button className={flip ? "on" : ""} onClick={() => setFlip(true)}>Upside-Down</button><button className={!flip ? "on" : ""} onClick={() => setFlip(false)}>Right side up</button></div>
      </div>
      <div className="up-wrap" style={{ transform: on ? "rotate(180deg)" : "none", marginBottom: 14 }}>
        <div style={{ transform: on ? "rotate(180deg)" : "none", transition: "transform .8s" }}>
          <Panel title="Decoy sandbox" tag={`${quarantined} agent(s) caged · ${entries.length} captured actions`} glow style={{ padding: 8 }}><UpsideScene n={entries.length} height={400} /></Panel>
        </div>
      </div>
      <Panel title="Canary tripwire" tag="confirmed exfiltration" glow style={{ marginBottom: 14 }}>
        <div className="dim tiny" style={{ marginBottom: 8 }}>Every decoy credential carries a unique canary. If one is ever seen outside the sandbox (a log, a paste site, a login attempt) paste it here: the attacker's copy is proven, and the agent is isolated (Tier 4 / REVOKE). {cans.length} canaries issued.</div>
        <div className="row" style={{ gap: 8 }}><input style={{ flex: 1 }} placeholder={cans[0] ? `e.g. AKIA${cans[0].canary.toUpperCase()}CANARY` : "quarantine an agent first, then paste a canary key"} value={cv} onChange={(e) => setCv(e.target.value)} /><button className="btn primary" onClick={check} disabled={!cv}>Check sighting</button>{cans[0] && <button className="btn ghost sm" onClick={() => setCv(`AKIA${cans[0].canary.toUpperCase()}CANARY`)}>use latest</button>}</div>
        {cr && <div className="chip" style={{ marginTop: 10, color: cr.found ? "var(--red2)" : "var(--green)" }}>{cr.found ? `✗ CONFIRMED: canary ${cr.canary} belongs to ${cr.agent}. REVOKE (Tier 4), alert ${cr.alert}.` : "✓ not one of our canaries"}</div>}
      </Panel>
      {entries.length === 0 && <Panel><div className="dim">Nothing is isolated. Launch the <b>Prompt injection</b> attack from the Attack Lab, then come back: the captured session appears here in real time.</div></Panel>}
      <div className="grid">
        {entries.slice(0, 12).map((e) => (
          <Panel key={e.event_id} title={`${e.display} · ${e.tool}`} tag={clock(e.ts)}>
            <div className="two" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <div><div className="tiny dim" style={{ marginBottom: 4 }}>WHAT THE ATTACKER SEES (fake)</div><div className="mirror-col fake">{e.attacker_saw}</div></div>
              <div><div className="tiny dim" style={{ marginBottom: 4 }}>WHAT WE RECORDED (real)</div><div className="mirror-col real">{`target   ${e.target}\npayload  ${fmtBytes(e.bytes)} (held)\ncanary   ${e.canary}\n` + e.we_recorded.map((r) => "• " + r).join("\n")}</div></div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
