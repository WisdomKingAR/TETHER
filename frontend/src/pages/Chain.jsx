import React, { useEffect, useState } from "react";
import { Panel, LevelBadge } from "../components/ui.jsx";
import { useStore, toast } from "../store.js";
import { api } from "../api.js";

function decode(tok) { try { const [h, p] = tok.split("."); const d = (x) => JSON.parse(atob(x.replace(/-/g, "+").replace(/_/g, "/"))); return [d(h), d(p)]; } catch { return [{}, {}]; } }

export default function Chain() {
  const s = useStore(); const [g, setG] = useState(null); const [agent, setAgent] = useState("procurement"); const [tok, setTok] = useState(null); const [scope, setScope] = useState([]); const [ex, setEx] = useState(null);
  useEffect(() => { api.get("/api/delegation").then(setG); const t = setInterval(() => api.get("/api/delegation").then(setG), 3000); return () => clearInterval(t); }, []);
  const load = () => api.get(`/api/tokens/${agent}`).then((t) => { setTok(t); setScope((t.current && t.current.scope) || []); setEx(null); });
  useEffect(() => { load(); }, [agent, s.agents[agent]?.level]);
  const exchange = async () => { try { setEx(await api.post("/api/token/exchange", { agent, scope, ttl: 300 })); toast({ title: "Token exchanged (RFC 8693)", body: "Subject token revoked; narrowed token issued with an actor claim.", to: "/chain" }); load(); } catch (e) { toast({ title: "Exchange failed", body: String(e.message).slice(0, 90), to: "/chain" }); } };
  const [h, p] = tok && tok.token ? decode(tok.token) : [{}, {}];
  const base = { procurement: [120, 70], pricing: [120, 230], hr_help: [420, 70], code_review: [420, 150], finance_recon: [420, 230] };
  const extras = (g?.nodes || []).filter((n) => !base[n.id]);           // spawned agents get a row along the bottom
  const pos = { ...base }; extras.forEach((n, i) => { pos[n.id] = [60 + (i % 6) * 90, 325 + Math.floor(i / 6) * 70]; });
  const at = (id) => pos[id] || [280, 150];
  const H = 310 + Math.ceil(extras.length / 6) * 70;
  return (
    <div className="page">
      <h1 className="h1">Chain of Custody</h1><p className="sub">Authority may only shrink along a delegation chain. Each hop carries a signed receipt (an RFC 8693 actor chain); a child that asks for more than its parent granted is flagged by the delegation plane. Below, exchange a live token and watch its scope narrow.</p>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)" }}>
        <div className="grid" style={{ alignContent: "start" }}>
          <Panel title="Delegation graph" glow>
            {g && (
              <svg viewBox={`0 0 560 ${H}`} width="100%" style={{ display: "block" }}>
                <defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#c08bff" /></marker></defs>
                {g.edges.map((e) => { const a = at(e.parent), b = at(e.child); return <g key={e.child}><line x1={a[0]} y1={a[1] + 22} x2={b[0]} y2={b[1] - 22} stroke="#c08bff" strokeWidth="2" markerEnd="url(#ar)" strokeDasharray="6 4"><animate attributeName="stroke-dashoffset" from="20" to="0" dur="1.2s" repeatCount="indefinite" /></line>
                  <text x={a[0] + 12} y={(a[1] + b[1]) / 2} fill="#c08bff" fontSize="11" fontFamily="JetBrains Mono">receipt: {e.receipt.granted.length} of {e.receipt.requested.length} tools</text></g>; })}
                {g.nodes.map((n) => { const [x, y] = at(n.id); const col = n.level >= 3 ? "#ff3b3b" : n.color; return (
                  <g key={n.id} onClick={() => setAgent(n.id)} style={{ cursor: "pointer" }}>
                    <circle cx={x} cy={y} r="26" fill="#0d070d" stroke={col} strokeWidth={agent === n.id ? 4 : 2} style={{ filter: `drop-shadow(0 0 ${n.level >= 3 ? 14 : 6}px ${col})` }} />
                    <text x={x} y={y + 4} textAnchor="middle" fill="#fff" fontFamily="Cinzel" fontWeight="700" fontSize="13">{Math.round(n.risk)}</text>
                    <text x={x} y={y + 44} textAnchor="middle" fill="#f4e9dc" fontSize="11.5" fontFamily="JetBrains Mono">{n.display}</text>
                    <text x={x} y={y + 58} textAnchor="middle" fill={col} fontSize="10" fontFamily="JetBrains Mono">L{n.level}{n.taint ? " · T2" : ""}</text>
                  </g>); })}
              </svg>
            )}
          </Panel>
          {g?.edges.map((e) => (
            <Panel key={e.child} title={`Receipt: ${e.parent} → ${e.child}`} tag={e.receipt.standard}>
              <div className="tiny dim">granted scope (parent ∩ child)</div><div className="tagrow" style={{ margin: "4px 0 8px" }}>{e.receipt.granted.map((t) => <span key={t} className="chip ok">{t}</span>)}</div>
              <div className="tiny dim">requested but dropped (attenuation)</div><div className="tagrow" style={{ margin: "4px 0 0" }}>{e.receipt.dropped.length ? e.receipt.dropped.map((t) => <span key={t} className="chip bad">{t}</span>) : <span className="dim tiny">none</span>}</div>
            </Panel>
          ))}
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <Panel title="Token vault" tag={agent} glow>
            <div className="seg" style={{ marginBottom: 10, flexWrap: "wrap" }}>{s.order.map((a) => <button key={a} className={a === agent ? "on" : ""} onClick={() => setAgent(a)}>{a.replace("_", " ")}</button>)}</div>
            {tok && tok.token && <>
              <div className="mono tiny" style={{ wordBreak: "break-all", padding: 10, borderRadius: 8, background: "rgba(0,0,0,.5)", border: "1px solid var(--line2)", lineHeight: 1.5 }}>
                <span style={{ color: "#ff6a5a" }}>{tok.token.split(".")[0]}</span>.<span style={{ color: "#7fd4ff" }}>{tok.token.split(".")[1]}</span>.<span style={{ color: "#c08bff" }}>{(tok.token.split(".")[2] || "").slice(0, 32)}…</span>
              </div>
              <div className="two" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 10 }}>
                <pre className="mono tiny" style={{ margin: 0, color: "#ff9a8a" }}>{JSON.stringify(h, null, 1)}</pre>
                <pre className="mono tiny" style={{ margin: 0, color: "#9fdcff", whiteSpace: "pre-wrap" }}>{JSON.stringify({ ...p, scope: (p.scope || "").split(" ").length + " scopes" }, null, 1)}</pre>
              </div>
              <div className="ptitle" style={{ marginTop: 14, fontSize: 11 }}>RFC 8693 token exchange · scope can only shrink</div>
              <div className="tagrow">{((tok.current && tok.current.scope) || []).map((t) => <button key={t} className="chip" style={{ cursor: "pointer", color: scope.includes(t) ? "#fff" : "var(--dim)", background: scope.includes(t) ? "rgba(192,139,255,.25)" : "transparent", borderColor: scope.includes(t) ? "var(--violet)" : "var(--line2)", textDecoration: scope.includes(t) ? "none" : "line-through" }} onClick={() => setScope(scope.includes(t) ? scope.filter((x) => x !== t) : [...scope, t])}>{t}</button>)}</div>
              <div className="row" style={{ marginTop: 10 }}><button className="btn primary" onClick={exchange}>Exchange → narrowed token (5 min)</button><span className="tiny dim">{tok.revoked_count} token(s) revoked so far</span></div>
              {ex && <div className="tiny mono" style={{ marginTop: 8, color: "var(--green)" }}>✓ issued · grant_type=…token-exchange · scope: {ex.scope.split(" ").length} · expires_in {ex.expires_in}s</div>}
            </>}
          </Panel>
          <Panel title="Why this matters"><div className="tiny dim" style={{ lineHeight: 1.7 }}>A compromised sub-agent normally launders its parent's authority. Here the receipt makes the parent the ceiling: whatever the child asks for beyond it is a delegation-plane signal (P5), taint from the child's untrusted input travels up the chain, and the parent's risk rises while its own legitimate tools keep running.</div></Panel>
        </div>
      </div>
    </div>
  );
}
