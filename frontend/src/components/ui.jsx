import React, { useEffect, useRef, useState } from "react";
import { LEVEL_COLORS, LEVEL_NAMES } from "../api.js";

export function Panel({ title, tag, className = "", children, style, glow, ...rest }) {
  const ref = useRef();
  const move = (e) => { const r = ref.current.getBoundingClientRect(); ref.current.style.setProperty("--mx", e.clientX - r.left + "px"); ref.current.style.setProperty("--my", e.clientY - r.top + "px"); };
  return (
    <div ref={ref} className={`panel ${glow ? "glow" : ""} ${className}`} style={style} onMouseMove={move} {...rest}>
      {title && <div className="ptitle">{title}{tag && <span className="tag">{tag}</span>}</div>}
      {children}
    </div>
  );
}

export function Tilt({ children, className = "", max = 9, ...rest }) {
  const ref = useRef();
  const onMove = (e) => {
    const r = ref.current.getBoundingClientRect(); const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    ref.current.style.transform = `perspective(800px) rotateY(${x * max}deg) rotateX(${-y * max}deg) translateZ(6px)`;
  };
  const off = () => { ref.current.style.transform = ""; };
  return <div ref={ref} className={`tilt ${className}`} onMouseMove={onMove} onMouseLeave={off} {...rest}>{children}</div>;
}

export const LevelBadge = ({ level }) => <span className="lvl" style={{ background: LEVEL_COLORS[level] }}>L{level} {LEVEL_NAMES[level]}</span>;

export function RiskBar({ value, color }) {
  const c = color || (value >= 70 ? "#ff3b3b" : value >= 50 ? "#f08a3c" : value >= 30 ? "#e8c34a" : "#6cc58a");
  return <div className="riskbar"><i style={{ width: Math.min(100, value) + "%", background: c, boxShadow: `0 0 10px ${c}` }} /></div>;
}

export function CountUp({ to, dur = 1400, suffix = "", decimals = 0 }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const t0 = performance.now();
    const id = setInterval(() => { const p = Math.min(1, (performance.now() - t0) / dur); setV(to * (1 - Math.pow(1 - p, 3))); if (p >= 1) clearInterval(id); }, 30);
    return () => clearInterval(id);
  }, [to]);
  return <>{v.toFixed(decimals)}{suffix}</>;
}

/* ------------------------------------------------------------------ SVG charts */
export function Spark({ data, w = 220, h = 46, color = "#ff3b3b", fill = true, max = 100 }) {
  if (!data || data.length < 2) return <svg width={w} height={h} />;
  const pts = data.map((d, i) => [(i / (data.length - 1)) * w, h - 3 - (Math.min(d, max) / max) * (h - 6)]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const id = "g" + color.replace("#", "");
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".45" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <line x1="0" x2={w} y1={h - 3 - 0.7 * (h - 6)} y2={h - 3 - 0.7 * (h - 6)} stroke="#ff3b3b" strokeOpacity=".25" strokeDasharray="3 4" />
      {fill && <path d={line + ` L${w} ${h} L0 ${h} Z`} fill={`url(#${id})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth="1.8" style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
    </svg>
  );
}

export function LineChart({ series, w = 560, h = 220, xs, yMax = 100, bands = true, xLabel, marks = [] }) {
  const pad = { l: 34, r: 10, t: 10, b: 22 }; const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const n = Math.max(...series.map((s) => s.data.length), 2);
  const X = (i) => pad.l + (i / (n - 1)) * iw, Y = (v) => pad.t + ih - (Math.min(v, yMax) / yMax) * ih;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: "block" }}>
      {bands && [[30, 50, "#e8c34a"], [50, 70, "#f08a3c"], [70, 95, "#ff3b3b"]].map(([a, b, c]) => <rect key={a} x={pad.l} y={Y(b)} width={iw} height={Y(a) - Y(b)} fill={c} opacity=".07" />)}
      {[0, 25, 50, 75, 100].map((t) => <g key={t}><line x1={pad.l} x2={w - pad.r} y1={Y(t)} y2={Y(t)} stroke="#fff" strokeOpacity=".07" /><text x={pad.l - 6} y={Y(t) + 4} fontSize="10" fill="#a8968c" textAnchor="end" fontFamily="JetBrains Mono">{t}</text></g>)}
      {series.map((s) => {
        const pts = s.data.map((d, i) => (d == null ? null : [X(i), Y(d)])).filter(Boolean);
        const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
        return <g key={s.name}><path d={d} fill="none" stroke={s.color} strokeWidth={s.bold ? 2.6 : 1.8} strokeDasharray={s.dash} style={{ filter: s.bold ? `drop-shadow(0 0 6px ${s.color})` : "none" }} />
          {s.dots && pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="3.6" fill={s.color} stroke="#000" />)}</g>;
      })}
      {marks.map((m) => <g key={m.i}><line x1={X(m.i)} x2={X(m.i)} y1={pad.t} y2={h - pad.b} stroke={m.color || "#7fd4ff"} strokeDasharray="4 3" /><text x={X(m.i) + 4} y={pad.t + 11} fontSize="10" fill={m.color || "#7fd4ff"} fontFamily="JetBrains Mono">{m.label}</text></g>)}
      {xs && xs.map((l, i) => <text key={i} x={X(i)} y={h - 6} fontSize="10" fill="#a8968c" textAnchor="middle" fontFamily="JetBrains Mono">{l}</text>)}
      {xLabel && <text x={w - pad.r} y={h - 6} fontSize="10" fill="#6d5f59" textAnchor="end">{xLabel}</text>}
    </svg>
  );
}

export function PlaneBars({ planes, labels, colors }) {
  const entries = Object.entries(planes).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map((e) => e[1]), 1);
  return (
    <div className="grid" style={{ gap: 8 }}>
      {entries.length === 0 && <div className="dim tiny">no plane contributed yet</div>}
      {entries.map(([k, v]) => (
        <div key={k}>
          <div className="row tiny" style={{ justifyContent: "space-between", marginBottom: 3 }}><span style={{ color: colors[k] }}>{labels[k]}</span><span className="mono">+{v.toFixed(0)}</span></div>
          <div className="riskbar" style={{ height: 8 }}><i style={{ width: (v / max) * 100 + "%", background: colors[k], boxShadow: `0 0 12px ${colors[k]}` }} /></div>
        </div>
      ))}
    </div>
  );
}

export function Radial({ value, size = 150, label = "RISK" }) {
  const r = size / 2 - 12, c = 2 * Math.PI * r, v = Math.min(100, value);
  const col = v >= 70 ? "#ff3b3b" : v >= 50 ? "#f08a3c" : v >= 30 ? "#e8c34a" : "#6cc58a";
  return (
    <svg width={size} height={size} style={{ display: "block" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#fff" strokeOpacity=".08" strokeWidth="10" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth="10" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dashoffset .6s, stroke .4s", filter: `drop-shadow(0 0 10px ${col})` }} />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fontFamily="Cinzel" fontWeight="900" fontSize={size / 3.2} fill="#fff">{Math.round(v)}</text>
      <text x="50%" y={size / 2 + size / 5} textAnchor="middle" fontSize="10" fill="#a8968c" letterSpacing="3">{label}</text>
    </svg>
  );
}

export function Heat({ m, labels, size = 30 }) {
  const mx = Math.max(...m.flat());
  return (
    <svg width={labels.length * size + 70} height={labels.length * size + 22}>
      {m.map((row, i) => row.map((v, j) => <rect key={i + "-" + j} x={70 + j * size} y={i * size} width={size - 2} height={size - 2} rx="3" fill="#ff3b3b" opacity={0.08 + 0.92 * (v / mx)} />))}
      {labels.map((l, i) => <text key={"l" + i} x="66" y={i * size + size / 2 + 3} fontSize="9.5" textAnchor="end" fill="#a8968c" fontFamily="JetBrains Mono">{l}</text>)}
      {labels.map((l, i) => <text key={"c" + i} x={70 + i * size + size / 2} y={labels.length * size + 12} fontSize="9" textAnchor="middle" fill="#6d5f59" fontFamily="JetBrains Mono">{l.slice(0, 4)}</text>)}
    </svg>
  );
}
