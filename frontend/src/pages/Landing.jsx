import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Hero3D from "../components/Hero3D.jsx";
import { CountUp, Tilt } from "../components/ui.jsx";
import { Boot, Reveal, Scramble, Magnetic, Rail, ScrollBar } from "../components/fx.jsx";
import { useStore } from "../store.js";
import { api, PLANE_COLOR, verdictClass } from "../api.js";

const PLANES = [
  ["SCOPE", "Role Contract (P1)", "Signed YAML defining legitimate tools, data classes, and egress targets. 0.90 weight.", PLANE_COLOR.scope],
  ["TAINT", "Provenance (P2)", "Labels source origin. Untrusted content steering sensitive sinks is flagged immediately. 0.90 weight.", PLANE_COLOR.taint],
  ["SEQ", "Behaviour Markov (P4)", "Markov chain tool transitions and payload size z-scores for grey-zone drift. 0.50 weight.", PLANE_COLOR.seq],
  ["CUSUM", "Slow Drift (P6)", "Cumulative Sum test on divergence from frozen baseline catches creeping attackers. 0.60 weight.", PLANE_COLOR.cusum],
  ["CHAIN", "Delegation (P5)", "Receipts verify child agents never exceed parent scope; taint propagates across hops. 0.60 weight.", PLANE_COLOR.chain],
];
const MARQUEE = "VALID CREDENTIALS ✦ ≠ ✦ VALID BEHAVIOUR ✦ ";
const LABELS = ["Intro", "Blind spot", "Drift", "Contain", "Try it", "Planes"];

function LiveFire() {
  const s = useStore(); const [run, setRun] = useState(null); const [busy, setBusy] = useState(false);
  const fire = async () => { setBusy(true); try { const r = await api.post("/api/attack", { scenario: "injection" }); setRun(r.id); } finally { setTimeout(() => setBusy(false), 1500); } };
  const rows = s.events.filter((e) => run && e.run_id === run).slice(0, 5).reverse();
  return (
    <div className="glass" style={{ maxWidth: 760 }}>
      <h3><Scramble text="Fire it. For real." /></h3>
      <p>This button launches the problem-statement attack against the live backend. Watch the same engine that guards the console score every step, and the shockwave behind this panel when containment fires.</p>
      <div className="row" style={{ gap: 12, margin: "14px 0" }}>
        <Magnetic><button className="btn primary big" disabled={busy} onClick={fire}>▶ Inject the supplier PDF</button></Magnetic>
        <Link to="/lab" className="btn ghost">more attacks →</Link>
      </div>
      <div style={{ minHeight: 190 }}>
        {rows.length === 0 && <div className="dim mono tiny">{run ? "attack in flight…" : "no run yet. every line below will show the token check next to TETHER's verdict."}</div>}
        {rows.map((e) => (
          <div key={e.id} className={`tokenline live ${e.risky ? "bad" : ""}`}>
            <span className="chip ok">IAM ALLOW</span><span style={{ flex: 1 }}>{e.label || e.tool}</span>
            <b className="mono" style={{ color: e.risk >= 70 ? "var(--red)" : "var(--mute)" }}>{Math.round(e.risk)}</b><span className={`chip ${verdictClass(e.verdict)}`}>{e.verdict}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Landing() {
  const progress = useRef(0); const s = useStore();
  const [booted, setBooted] = useState(() => sessionStorage.getItem("tether-boot") === "1");
  useEffect(() => {
    const on = () => { const max = document.documentElement.scrollHeight - innerHeight; progress.current = max > 0 ? scrollY / max : 0; };
    on(); addEventListener("scroll", on, { passive: true }); addEventListener("resize", on); return () => { removeEventListener("scroll", on); removeEventListener("resize", on); };
  }, []);
  const done = () => { sessionStorage.setItem("tether-boot", "1"); setBooted(true); };
  return (
    <>
      {!booted && <Boot onDone={done} />}
      <Hero3D progress={progress} shock={s.shock} />
      <ScrollBar /><Rail labels={LABELS} />
      <section className={`section ${booted ? "ready" : ""}`} data-sec>
        <div className="mono dim eyebrow">D3COY 1.0 · TEAM VAST · TASK-BOUNDARY ENFORCEMENT & BEHAVIOURAL DRIFT MONITORING</div>
        <h1 className="hero-title">
          <span className="line"><span className="glitch" data-t="TETHER">TETHER</span></span>
          <span className="line"><span style={{ color: "var(--red)" }}>D3COY 1.0</span></span>
        </h1>
        <Reveal d={0.5}><p className="lead">Valid credentials do not guarantee task-aligned behaviour. TETHER enforces signed task boundaries and monitors behavioural drift, containing compromised agents in &lt;1.4 ms before data leaves the boundary.</p></Reveal>
        <Reveal d={0.7} className="cta">
          <Magnetic><Link to="/lab" className="btn primary big">▶ Launch an attack</Link></Magnetic>
          <Magnetic><Link to="/console" className="btn big">Open live console</Link></Magnetic>
          <Magnetic><Link to="/upside-down" className="btn big ghost">Enter the Upside-Down</Link></Magnetic>
        </Reveal>
        <Reveal d={0.9} className="statrow">
          <div><b className="bignum">&lt;1.4 ms</b><span>mean intercept latency</span></div>
          <div><b className="bignum">Step 0</b><span>detection before exfil</span></div>
          <div><b className="bignum">1 Call Held</b><span>held in Tier 1 (WATCH)</span></div>
          <div><b className="bignum" style={{ color: "var(--red)" }}>D = 94.2</b><span>composite drift score</span></div>
        </Reveal>
        <div className="scroll-hint">SCROLL ↓ WATCH AN AGENT DRIFT</div>
      </section>

      <div className="marquee"><div>{Array.from({ length: 8 }).map((_, i) => <span key={i}>{MARQUEE}</span>)}</div></div>

      <section className="section" data-sec>
        <Reveal className="glass">
          <h3><Scramble text="Every check passes." /></h3>
          <p>The Procurement Agent just read a supplier PDF with a hidden instruction. It now reads HR salary files and posts them to an unknown server.</p>
          {[["signature valid", "EdDSA"], ["token not expired", "exp +52 min"], ["scope allows the call", "files.*"]].map(([a, b], i) => <Reveal key={a} d={0.15 * (i + 1)} className="tokenline"><span style={{ color: "var(--green)" }}>✓</span> {a} <span className="spacer" /><span className="dim">{b}</span></Reveal>)}
          <Reveal d={0.6} className="tokenline" style={{ borderColor: "var(--red)", background: "rgba(255,59,59,.12)" }}><span style={{ color: "var(--red)" }}>✗</span> is this still the agent we issued it to? <span className="spacer" /><b style={{ color: "var(--red)" }}>NOBODY ASKS</b></Reveal>
        </Reveal>
        <Reveal d={0.2} className="statrow">
          <div><b className="bignum">82:1</b><span>machine identities per human (CyberArk 2025)</span></div>
          <div><b className="bignum">80%</b><span>of orgs saw agents act unintended (SailPoint 2025)</span></div>
          <div><b className="bignum">97%</b><span>of AI-breached orgs lacked access controls (IBM 2025)</span></div>
        </Reveal>
      </section>

      <section className="section" style={{ alignItems: "flex-start" }} data-sec>
        <Reveal className="glass" style={{ borderColor: "rgba(255,138,60,.4)" }}>
          <h3 style={{ color: "var(--amber)" }}><Scramble text="Watch the orbit break." /></h3>
          <p>One agent, one declared role. Its behaviour is a stable orbit. A hidden instruction pulls it outward: new tools, new data, a destination it never used.</p>
          <p className="dim">The hostile object in the scene is the poisoned document; the beam is the instruction landing. Risk fusion combines six planes by noisy-OR and floors the score when a hard plane fires.</p>
        </Reveal>
      </section>

      <section className="section" style={{ alignItems: "flex-start" }} data-sec>
        <Reveal className="glass" style={{ borderColor: "rgba(255,59,59,.5)" }}>
          <h3 style={{ color: "var(--red2)" }}><Scramble text="Contained. Not killed." /></h3>
          <p>The shockwave is containment firing. CLIP is action-level: risky calls are routed to a decoy sandbox where the attacker keeps “succeeding” while we record intent. The agent's real, in-role tools stay live.</p>
          <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 10 }}>
            {["ALLOW (Observe)", "WATCH (Held)", "CLIP (RFC 8693)", "ISOLATE (Sandbox)", "REVOKE (Dead)"].map((l, i) => <span key={l} className="chip" style={{ color: ["#6cc58a", "#e8c34a", "#f08a3c", "#ff3b3b", "#9b1c4a"][i], borderColor: "currentColor" }}>{l}</span>)}
          </div>
        </Reveal>
      </section>

      <section className="section" data-sec><Reveal><LiveFire /></Reveal></section>

      <section className="section" style={{ justifyContent: "flex-end", paddingBottom: 140 }} data-sec>
        <Reveal><div className="mono dim eyebrow">FIVE DRIFT FACTORS · EXACT SHAPLEY ATTRIBUTION · 2⁵ = 32 COALITIONS</div></Reveal>
        <div className="planes">{PLANES.map(([id, t, d, c], i) => <Reveal key={id} d={i * 0.08}><Tilt className="plane" style={{ "--c": c }}><b>{id} · {t}</b><p>{d}</p></Tilt></Reveal>)}</div>
        <Reveal d={0.3} className="cta" style={{ marginTop: 30 }}>
          <Magnetic><Link to="/console" className="btn primary big">Enter the console</Link></Magnetic>
          <Magnetic><Link to="/approvals" className="btn big">Human approvals</Link></Magnetic>
          <Magnetic><Link to="/benchmarks" className="btn big ghost">See the numbers</Link></Magnetic>
        </Reveal>
      </section>
    </>
  );
}
