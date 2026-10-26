import React, { useEffect, useState } from "react";
import { Panel } from "../components/ui.jsx";
import { useStore, toast } from "../store.js";
import { api, clock } from "../api.js";

export default function Ledger() {
  const s = useStore(); const [rows, setRows] = useState([]); const [v, setV] = useState(null);
  const load = async () => { const [r, ver] = await Promise.all([api.get("/api/audit?limit=24"), api.get("/api/audit/verify")]); setRows(r.slice().reverse()); setV(ver); };
  useEffect(() => { load(); const t = setInterval(load, 2500); return () => clearInterval(t); }, []);
  const tamper = async () => { const r = await api.post("/api/audit/tamper"); toast({ title: r.ok ? "Record silently edited" : "Not enough records", body: r.ok ? `idx ${r.idx} changed from DENY to ALLOW. Verify the chain.` : r.reason, to: "/ledger" }); load(); };
  return (
    <div className="page">
      <h1 className="h1">Tamper-evident Ledger</h1><p className="sub">Every decision is appended to a hash-chained log: each record commits to the one before it. Silently editing history breaks every hash after it, so an incident review can trust what the gateway says it did.</p>
      <div className="row" style={{ gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <Panel glow style={{ minWidth: 300 }}><div className="row" style={{ gap: 14 }}><div style={{ fontSize: 34, color: v?.ok ? "var(--green)" : "var(--red)", textShadow: "0 0 24px currentColor" }}>{v?.ok ? "✓" : "✗"}</div><div><div className="mono" style={{ fontSize: 15 }}>{v?.ok ? "Chain intact" : `Broken at record #${v?.first_broken}`}</div><div className="tiny dim">{v?.records} records · head {v?.head.slice(0, 16)}…</div></div></div></Panel>
        <button className="btn" onClick={load}>Verify now</button><button className="btn ghost" onClick={tamper}>☠ Tamper with a record</button><button className="btn ghost" onClick={async () => { await api.post("/api/audit/reseal"); toast({ title: "Chain re-sealed", body: "After review, hashes are recomputed.", to: "/ledger" }); load(); }}>Re-seal after review</button>
      </div>
      <Panel title="Latest records" tag="oldest → newest">
        <div className="chain">
          {rows.map((r) => (
            <div key={r.idx} className={`block ${v && !v.ok && r.idx >= v.first_broken ? "broken" : ""}`}>
              <div style={{ color: "var(--green)", fontWeight: 700 }}>#{r.idx} · {clock(r.ts)}</div>
              <div style={{ margin: "4px 0" }}>{r.payload.agent}<br /><span className="dim">{r.payload.tool}</span></div>
              <div>risk {Math.round(r.payload.risk)} · {r.payload.verdict}{r.payload.tampered ? " ⚠" : ""}</div>
              <div className="dim" style={{ marginTop: 4 }}>prev {r.prev.slice(0, 8)}</div><div style={{ color: "#fff" }}>hash {r.hash.slice(0, 8)}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
