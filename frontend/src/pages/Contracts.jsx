import React, { useEffect, useState } from "react";
import { Panel, Tilt } from "../components/ui.jsx";
import { useStore, toast } from "../store.js";
import { api } from "../api.js";

function Chips({ items, onChange, deny, placeholder }) {
  const [v, setV] = useState("");
  return (
    <div className="tagrow" style={{ alignItems: "center" }}>
      {items.map((x) => <span key={x} className={`edit-chip ${deny ? "deny" : ""}`}>{x}<button onClick={() => onChange(items.filter((y) => y !== x))}>×</button></span>)}
      <input value={v} placeholder={placeholder} style={{ width: 150, padding: "4px 8px" }} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && v.trim()) { onChange([...new Set([...items, v.trim()])]); setV(""); } }} />
    </div>
  );
}

const yaml = (c) => [`agent: ${c.agent}   # v${c.version}`, `owner: ${c.owner}`, `allow_tools: [${c.allow_tools.join(", ")}]`, `allow_classes: [${c.allow_classes.join(", ")}]`, `deny_classes: [${c.deny_classes.join(", ")}]`, `egress: [${c.egress.join(", ")}]`, `rate_per_min: ${c.rate_per_min}`, `max_bytes_out: ${Math.round(c.max_bytes_out / 1000)} KB/min`, `delegate_to: [${c.delegate_to.join(", ")}]`, `decoys: [${c.decoys.join(", ")}]`, `signature: ${c.signature}`].join("\n");

export default function Contracts() {
  const s = useStore(); const [id, setId] = useState("procurement"); const [data, setData] = useState(null); const [draft, setDraft] = useState(null); const [wi, setWi] = useState(null); const [sug, setSug] = useState(null);
  const load = () => api.get(`/api/contracts/${id}`).then((d) => { setData(d); setDraft({ ...d.contract }); setWi(null); setSug(null); });
  useEffect(() => { load(); }, [id]);
  if (!data || !draft) return <div className="page"><p className="dim">loading…</p></div>;
  const patch = { allow_tools: draft.allow_tools, allow_classes: draft.allow_classes, deny_classes: draft.deny_classes, egress: draft.egress, decoys: draft.decoys, rate_per_min: draft.rate_per_min, max_bytes_out: draft.max_bytes_out };
  const dirty = JSON.stringify(patch) !== JSON.stringify({ allow_tools: data.contract.allow_tools, allow_classes: data.contract.allow_classes, deny_classes: data.contract.deny_classes, egress: data.contract.egress, decoys: data.contract.decoys, rate_per_min: data.contract.rate_per_min, max_bytes_out: data.contract.max_bytes_out });
  const set = (k, v) => setDraft({ ...draft, [k]: v });
  const toggleTool = (t) => set("allow_tools", draft.allow_tools.includes(t) ? draft.allow_tools.filter((x) => x !== t) : [...draft.allow_tools, t]);
  const deploy = async () => { const c = await api.put(`/api/contracts/${id}`, patch); toast({ kind: "ok", title: `Contract v${c.version} signed`, body: "Canary window open for 5 minutes. Baselines re-anchor only after approval.", to: "/contracts" }); load(); };
  const canary = data.contract.canary_until && data.contract.canary_until * 1000 > Date.now();
  return (
    <div className="page">
      <h1 className="h1">Contract Studio</h1><p className="sub">The declared role is a signed contract. Edit it, replay the last 300 real events against your proposal before deploying (shadow what-if), or let TETHER draft one from observed behaviour. A signed bump opens a canary window so legitimate change is not mistaken for drift.</p>
      <div className="seg" style={{ marginBottom: 14, flexWrap: "wrap" }}>{s.order.map((a) => <button key={a} className={a === id ? "on" : ""} onClick={() => setId(a)}>{s.agents[a]?.display.replace(" Agent", "")}</button>)}</div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)" }}>
        <div className="grid" style={{ alignContent: "start" }}>
          <Panel title="Allowed tools" tag="click to toggle">
            <div className="tagrow">{data.catalog.map((t) => <button key={t.name} onClick={() => toggleTool(t.name)} className="chip" style={{ cursor: "pointer", padding: "5px 10px", color: draft.allow_tools.includes(t.name) ? "#fff" : "var(--dim)", background: draft.allow_tools.includes(t.name) ? "rgba(255,59,59,.22)" : "transparent", borderColor: draft.allow_tools.includes(t.name) ? "var(--red)" : "var(--line2)", textDecoration: draft.allow_tools.includes(t.name) ? "none" : "line-through" }}>{t.name}{t.sink ? " ⇢" : ""}</button>)}</div>
            <div className="tiny dim" style={{ marginTop: 6 }}>⇢ marks a sink (a tool that can send data out). Tool descriptions are hash-pinned: {Object.keys(draft.tool_hashes).length} pins.</div>
          </Panel>
          <div className="two" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <Panel title="Allowed data classes"><Chips items={draft.allow_classes} onChange={(v) => set("allow_classes", v)} placeholder="add class ⏎" /></Panel>
            <Panel title="Denied data classes"><Chips deny items={draft.deny_classes} onChange={(v) => set("deny_classes", v)} placeholder="add class ⏎" /></Panel>
            <Panel title="Approved egress (glob)"><Chips items={draft.egress} onChange={(v) => set("egress", v)} placeholder="*.example.com ⏎" /></Panel>
            <Panel title="Decoys (honey targets)"><Chips deny items={draft.decoys} onChange={(v) => set("decoys", v)} placeholder="path ⏎" /></Panel>
          </div>
          <Panel title="Limits">
            <div className="two" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <div><div className="tiny dim">rate per minute <b style={{ color: "#fff" }}>{draft.rate_per_min}</b></div><input type="range" min="10" max="400" value={draft.rate_per_min} onChange={(e) => set("rate_per_min", +e.target.value)} style={{ width: "100%" }} /></div>
              <div><div className="tiny dim">max bytes out / min <b style={{ color: "#fff" }}>{Math.round(draft.max_bytes_out / 1000)} KB</b></div><input type="range" min="20000" max="2000000" step="10000" value={draft.max_bytes_out} onChange={(e) => set("max_bytes_out", +e.target.value)} style={{ width: "100%" }} /></div>
            </div>
          </Panel>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <button className="btn" onClick={async () => setWi(await api.post(`/api/contracts/${id}/whatif`, patch))}>⏪ What-if replay</button>
            <button className="btn ghost" onClick={async () => setSug(await api.post(`/api/contracts/${id}/suggest`))}>✦ Learn from traces</button>
            <button className="btn primary" disabled={!dirty} onClick={deploy}>Sign & deploy v{data.contract.version + 1}</button>
            <button className="btn ghost sm" disabled={!dirty} onClick={() => setDraft({ ...data.contract })}>revert</button>
          </div>
          {wi && (
            <Panel title="What-if result" tag={`${wi.replayed} real events replayed`} glow>
              <div className="row" style={{ gap: 28 }}>
                <div className="stat"><b>{wi.fires_before}</b><span>fire today</span></div><div className="stat"><b style={{ color: wi.fires_after > wi.fires_before ? "var(--red)" : "var(--green)" }}>{wi.fires_after}</b><span>would fire</span></div>
                <div className="stat"><b style={{ color: "var(--amber)" }}>+{wi.newly_blocked}</b><span>newly flagged</span></div><div className="stat"><b style={{ color: "var(--green)" }}>−{wi.newly_allowed}</b><span>no longer flagged</span></div>
              </div>
              {wi.samples.length > 0 && <table className="t" style={{ marginTop: 10 }}><tbody>{wi.samples.map((x) => <tr key={x.id}><td className="mono">#{x.id}</td><td className="mono">{x.tool}</td><td className="dim">{x.target}</td><td><span className="chip warn">{x.change}</span></td><td className="tiny dim">{x.why[0]}</td></tr>)}</tbody></table>}
              {wi.samples.length === 0 && <div className="dim tiny" style={{ marginTop: 8 }}>No change in behaviour on the last {wi.replayed} events: safe to deploy.</div>}
            </Panel>
          )}
          {sug && (
            <Panel title="Suggested from observed behaviour" tag={`${sug.based_on} clean events`}>
              <div className="tiny dim">allow_tools</div><div className="tagrow">{sug.allow_tools.map((t) => <span key={t} className="chip">{t}</span>)}</div>
              <div className="tiny dim" style={{ marginTop: 6 }}>allow_classes</div><div className="tagrow">{sug.allow_classes.map((t) => <span key={t} className="chip">{t}</span>)}</div>
              <button className="btn sm" style={{ marginTop: 10 }} onClick={() => { setDraft({ ...draft, allow_tools: sug.allow_tools, allow_classes: sug.allow_classes }); setSug(null); }}>Apply to draft</button>
            </Panel>
          )}
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <Panel title="Signed contract" tag={`v${data.contract.version}`} glow>
            <pre className="mono" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6, whiteSpace: "pre-wrap", color: "#f2d9b8" }}>{yaml({ ...draft, version: data.contract.version, signature: data.contract.signature })}</pre>
            {canary && <div className="chip warn" style={{ marginTop: 10 }}>⏱ canary window open: drift judged against the new envelope</div>}
          </Panel>
          <Panel title="Why a contract">
            <div className="tiny dim" style={{ lineHeight: 1.7 }}>Protection starts at the agent's <b style={{ color: "#fff" }}>first call</b>: the contract needs no history. Learning (behaviour plane P4, drift P6) refines the picture but never decides what is allowed. Changes are versioned, signed (SHA-256 digest here, Ed25519 in production) and stamped on every event, so an auditor can always say which declared role an action was judged against.</div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
