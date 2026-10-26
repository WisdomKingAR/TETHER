import React, { Suspense, lazy, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useStore } from "./store.js";
import { api } from "./api.js";
import Landing from "./pages/Landing.jsx";
import { Cursor, Ticker } from "./components/fx.jsx";
const Console = lazy(() => import("./pages/Console.jsx"));
const Lab = lazy(() => import("./pages/Lab.jsx"));
const Alerts = lazy(() => import("./pages/Alerts.jsx"));
const Contracts = lazy(() => import("./pages/Contracts.jsx"));
const Upside = lazy(() => import("./pages/Upside.jsx"));
const Chain = lazy(() => import("./pages/Chain.jsx"));
const Ledger = lazy(() => import("./pages/Ledger.jsx"));
const Benchmarks = lazy(() => import("./pages/Benchmarks.jsx"));
const Approvals = lazy(() => import("./pages/Approvals.jsx"));
const Coverage = lazy(() => import("./pages/Coverage.jsx"));

class Boundary extends React.Component {
  constructor(p) { super(p); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidUpdate(prev) { if (prev.k !== this.props.k && this.state.err) this.setState({ err: null }); }
  render() {
    if (!this.state.err) return this.props.children;
    return <div className="page"><div className="panel glow"><div className="ptitle">This page hit an error</div><p className="sub">{String(this.state.err.message || this.state.err).slice(0, 200)}</p><button className="btn primary" onClick={() => this.setState({ err: null })}>Try again</button></div></div>;
  }
}

const LINKS = [["/console", "Console"], ["/lab", "Attack Lab"], ["/alerts", "Alerts"], ["/approvals", "Approvals"], ["/contracts", "Contracts"], ["/upside-down", "Upside-Down"], ["/chain", "Chain"], ["/ledger", "Ledger"], ["/coverage", "Coverage"], ["/benchmarks", "Benchmarks"]];

function Nav({ onPalette }) {
  const s = useStore();
  const open = Object.values(s.alerts).filter((a) => a.status === "open").length;
  return (
    <div className="nav">
      <Link to="/" className="brand"><i />TETHER <span className="chip" style={{ marginLeft: 6, fontSize: "0.65rem", padding: "1px 6px" }}>D3COY 1.0</span></Link>
      <div className="navlinks">
        {LINKS.map(([to, l]) => <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>{l}{to === "/alerts" && open > 0 ? ` · ${open}` : ""}{to === "/approvals" && s.pendingCount > 0 ? ` · ${s.pendingCount}` : ""}</NavLink>)}
      </div>
      <div className="navright">
        <span className={`chip ${s.mode === "enforce" ? "bad" : "shadow"}`}>{s.mode.toUpperCase()}</span>
        <span><i className={`dot ${s.connected ? "live" : ""}`} /> {s.connected ? "LIVE" : "OFFLINE"}</span>
        <button className="btn ghost sm" onClick={onPalette}>search <span className="kbd">⌘K</span></button>
      </div>
    </div>
  );
}

function Toasts() {
  const s = useStore(); const nav = useNavigate();
  return <div className="toasts">{s.toasts.map((t) => <div key={t.id} className="toast" onClick={() => nav(t.to)} style={{ cursor: "pointer" }}><b>⚠ {t.title}</b><p>{t.body}</p></div>)}</div>;
}

function Palette({ open, onClose }) {
  const nav = useNavigate(); const [q, setQ] = useState("");
  useEffect(() => { if (open) setQ(""); }, [open]);
  if (!open) return null;
  const items = [...LINKS, ["/", "Landing"], ["__inject", "Run: prompt injection attack"], ["__release", "Release all quarantined agents"], ["__reset", "Reset demo state"]].filter(([, l]) => l.toLowerCase().includes(q.toLowerCase()));
  const go = async (to) => {
    onClose();
    if (to === "__inject") { await api.post("/api/attack", { scenario: "injection" }); nav("/lab"); }
    else if (to === "__release") { for (const id of ["procurement", "pricing", "hr_help", "code_review", "finance_recon"]) await api.post(`/api/agents/${id}/release`); }
    else if (to === "__reset") await api.post("/api/reset");
    else nav(to);
  };
  return (
    <div className="cmdk" onClick={onClose}><div onClick={(e) => e.stopPropagation()}>
      <input autoFocus placeholder="Jump to a page or run an action…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && items[0]) go(items[0][0]); if (e.key === "Escape") onClose(); }} />
      <div style={{ marginTop: 8 }}>{items.map(([to, l]) => <a key={to} href="#" onClick={(e) => { e.preventDefault(); go(to); }}>{l}<span className="dim tiny mono">{to.startsWith("__") ? "action" : to}</span></a>)}</div>
    </div></div>
  );
}

export default function App() {
  const [pal, setPal] = useState(false); const loc = useLocation();
  useEffect(() => {
    const k = (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPal((v) => !v); } };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, []);
  useEffect(() => { window.scrollTo(0, 0); }, [loc.pathname]);
  return (
    <>
      <div className="noise" /><div className="vignette" />
      <Nav onPalette={() => setPal(true)} />
      <Suspense fallback={<div className="page"><p className="dim mono">loading…</p></div>}>
        <div key={loc.pathname.startsWith("/alerts") ? "/alerts" : loc.pathname} className={`route-wrap ${loc.pathname === "/" ? "plain" : ""}`}>
        <Boundary k={loc.pathname}><Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/console" element={<Console />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/alerts/:id" element={<Alerts />} />
          <Route path="/contracts" element={<Contracts />} />
          <Route path="/upside-down" element={<Upside />} />
          <Route path="/chain" element={<Chain />} />
          <Route path="/ledger" element={<Ledger />} />
          <Route path="/benchmarks" element={<Benchmarks />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/coverage" element={<Coverage />} />
        </Routes></Boundary>
        </div>
      </Suspense>
      <Cursor /><Ticker />
      <Toasts /><Palette open={pal} onClose={() => setPal(false)} />
    </>
  );
}
