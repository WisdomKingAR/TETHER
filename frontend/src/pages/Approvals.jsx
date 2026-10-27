import React, { useEffect, useState } from "react";
import { Panel, RiskBar } from "../components/ui.jsx";
import { useStore, toast } from "../store.js";
import { api, fmtBytes, clock } from "../api.js";

export default function Approvals() {
  const s = useStore(); const [d, setD] = useState({ pending: [], resolved: [] });
  const load = () => api.get("/api/approvals").then(setD).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 1500); return () => clearInterval(t); }, []);
  const decide = async (id, approve) => {
    const item = d.pending.find((x) => x.id === id);
    if (item) {
      const resolvedItem = { ...item, status: approve ? "approved" : "denied", resolved: Date.now() / 1000 };
      setD((prev) => ({
        pending: prev.pending.filter((x) => x.id !== id),
        resolved: [resolvedItem, ...prev.resolved].slice(0, 15),
      }));
    }
    try {
      await api.post(`/api/approvals/${id}`, { approve });
      toast({ title: approve ? "Approved" : "Denied", body: `Action #${id} resolved by a human and written to the audit ledger.`, to: "/approvals" });
    } catch (e) {
      console.error(e);
    }
    load();
  };
  const seedActions = async () => {
    try {
      const res = await api.post("/api/approvals/seed");
      if (res && res.pending) setD(res);
      else load();
      toast({ title: "Queue Seeded", body: "Added sample gray-zone actions to test human approval.", to: "/approvals" });
    } catch (e) {
      console.error(e);
    }
  };
  return (
    <div className="page">
      <div className="row" style={{ alignItems: "flex-end", marginBottom: 10 }}>
        <div style={{ flex: 1 }}>
          <h1 className="h1">Approval Queue</h1>
          <p className="sub" style={{ margin: 0 }}>The gray zone: an action is statistically odd but nothing is provably out of contract. TETHER does not guess. At Tier 1 (WATCH) it holds <i>that one action</i>, keeps the agent working, and asks a human. Every decision is appended to the tamper-evident ledger. Launch “Gray zone” in the Attack Lab to fill this queue.</p>
        </div>
        <button className="btn sm primary" onClick={seedActions} style={{ whiteSpace: "nowrap" }}>⚡ Seed Test Pending Actions</button>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr)" }}>
        <div className="grid" style={{ alignContent: "start" }}>
          {d.pending.length === 0 && (
            <Panel>
              <div className="dim">Nothing waiting. Run the <b>Gray zone</b> scenario from the Attack Lab, or click <b>Seed Test Pending Actions</b> above.</div>
            </Panel>
          )}
          {d.pending.map((p) => (
            <Panel key={p.id} glow className="alert-pulse" title={`${p.display} · ${p.tool}`} tag={`#${p.id} · ${clock(p.ts)}`}>
              <div className="row" style={{ gap: 18, alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <div className="mono tiny dim">target</div><div className="mono" style={{ marginBottom: 8 }}>{p.target || "—"} <span className="dim">· {fmtBytes(p.bytes)}</span></div>
                  {p.reasons.map((r, i) => <div key={i} className="tiny" style={{ padding: "3px 0" }}>• {r}</div>)}
                  <div style={{ marginTop: 8 }}><div className="tiny dim">D = {Math.round(p.risk)}</div><RiskBar value={p.risk} /></div>
                </div>
                <div className="grid" style={{ gap: 8 }}><button className="btn primary" onClick={() => decide(p.id, true)}>✓ Approve</button><button className="btn" onClick={() => decide(p.id, false)}>✗ Deny</button></div>
              </div>
            </Panel>
          ))}
        </div>
        <Panel title="Recently resolved" tag="written to the ledger">
          {d.resolved.length === 0 && <div className="dim tiny">no decisions yet</div>}
          <table className="t"><tbody>{d.resolved.map((p) => <tr key={p.id}><td className="mono">#{p.id}</td><td>{p.agent}</td><td className="mono">{p.tool}</td><td><span className={`chip ${p.status === "approved" ? "ok" : "bad"}`}>{p.status}</span></td></tr>)}</tbody></table>
        </Panel>
      </div>
    </div>
  );
}
