import React, { useEffect, useRef, useState } from "react";
import { useStore } from "../store.js";

/* ---------------------------------------------------------------- boot sequence */
const BOOT = ["mounting gateway · FastAPI · ASGI", "loading 5 role contracts … signatures verified", "arming decoys · canaries · taint tracker", "verifying audit chain … intact", "TETHER ONLINE · D3COY 1.0"];
export function Boot({ onDone }) {
  const [n, setN] = useState(0); const [out, setOut] = useState(false);
  useEffect(() => {
    const ids = BOOT.map((_, i) => setTimeout(() => setN(i + 1), 350 + i * 430));
    const a = setTimeout(() => setOut(true), 350 + BOOT.length * 430 + 350); const b = setTimeout(onDone, 350 + BOOT.length * 430 + 1150);
    return () => [...ids, a, b].forEach(clearTimeout);
  }, []);
  return (
    <div className={`boot ${out ? "out" : ""}`}>
      <div className="boot-star" />
      <div className="boot-lines mono">{BOOT.slice(0, n).map((l, i) => <div key={i} className={i === BOOT.length - 1 ? "last" : ""}><span className="dim">[{String(i).padStart(2, "0")}]</span> {l}</div>)}<span className="caret" /></div>
      <div className="boot-bar"><i style={{ width: (n / BOOT.length) * 100 + "%" }} /></div>
    </div>
  );
}

/* ---------------------------------------------------------------- cursor */
export function Cursor() {
  const dot = useRef(), ring = useRef(); const pos = useRef({ x: -100, y: -100, rx: -100, ry: -100, big: false });
  useEffect(() => {
    if (matchMedia("(pointer: coarse)").matches) return;
    const mv = (e) => { pos.current.x = e.clientX; pos.current.y = e.clientY; pos.current.big = !!e.target.closest?.("a,button,.tilt,.scard,.acard,input,textarea,select,[data-mag]"); };
    addEventListener("mousemove", mv);
    let raf; const loop = () => {
      const p = pos.current; p.rx += (p.x - p.rx) * 0.16; p.ry += (p.y - p.ry) * 0.16;
      if (dot.current) dot.current.style.transform = `translate(${p.x}px,${p.y}px)`;
      if (ring.current) ring.current.style.transform = `translate(${p.rx}px,${p.ry}px) scale(${p.big ? 1.9 : 1})`;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { removeEventListener("mousemove", mv); cancelAnimationFrame(raf); };
  }, []);
  return <><div ref={ring} className="cursor-ring" /><div ref={dot} className="cursor-dot" /></>;
}

/* ---------------------------------------------------------------- reveal + scramble + magnetic */
export function useInView(once = true, margin = "-12% 0px") {
  const ref = useRef(); const [on, setOn] = useState(false);
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); if (once) io.disconnect(); } else if (!once) setOn(false); }, { rootMargin: margin, threshold: 0.05 });
    ref.current && io.observe(ref.current); return () => io.disconnect();
  }, []);
  return [ref, on];
}
export function Reveal({ children, d = 0, as: T = "div", className = "", style, ...rest }) {
  const [ref, on] = useInView();
  return <T ref={ref} className={`reveal ${on ? "in" : ""} ${className}`} style={{ "--d": d + "s", ...style }} {...rest}>{children}</T>;
}

const GLYPHS = "ABCDEF0123456789#%&*+<>/\\=—";
export function Scramble({ text, dur = 900, as: T = "span", className = "", style }) {
  const [ref, on] = useInView(); const [out, setOut] = useState(text.replace(/\S/g, "·"));
  useEffect(() => {
    if (!on) return; const t0 = performance.now();
    const id = setInterval(() => {
      const p = Math.min(1, (performance.now() - t0) / dur);
      setOut(text.split("").map((c, i) => (c === " " || c === "\n" ? c : i / text.length < p ? c : GLYPHS[(Math.random() * GLYPHS.length) | 0])).join(""));
      if (p >= 1) { clearInterval(id); setOut(text); }
    }, 32);
    return () => clearInterval(id);
  }, [on, text]);
  return <T ref={ref} className={className} style={style}>{out}</T>;
}

export function Magnetic({ children, strength = 0.35 }) {
  const ref = useRef();
  const mv = (e) => { const r = ref.current.getBoundingClientRect(); ref.current.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * strength}px,${(e.clientY - r.top - r.height / 2) * strength}px)`; };
  return <span data-mag ref={ref} style={{ display: "inline-block", transition: "transform .25s cubic-bezier(.2,.9,.3,1.3)" }} onMouseMove={mv} onMouseLeave={() => (ref.current.style.transform = "")}>{children}</span>;
}

/* ---------------------------------------------------------------- live ticker */
export function Ticker() {
  const s = useStore(); const ev = s.events.slice(0, 16);
  if (!ev.length) return null;
  const row = ev.map((e) => (
    <span key={e.id} className={`tk ${e.risky ? "hot" : ""}`}><b>{e.agent}</b> {e.tool} <em>{Math.round(e.risk)}</em> {e.verdict}</span>
  ));
  return <div className="ticker"><div className="ticker-track">{row}{row}</div></div>;
}

/* ---------------------------------------------------------------- scroll progress + section rail */
export function ScrollBar() {
  const ref = useRef();
  useEffect(() => {
    const f = () => { const m = document.documentElement.scrollHeight - innerHeight; ref.current && (ref.current.style.transform = `scaleX(${m > 0 ? scrollY / m : 0})`); };
    addEventListener("scroll", f, { passive: true }); f(); return () => removeEventListener("scroll", f);
  }, []);
  return <div className="scrollbar"><i ref={ref} /></div>;
}

export function Rail({ labels }) {
  const [act, setAct] = useState(0);
  useEffect(() => {
    const f = () => { const secs = [...document.querySelectorAll("[data-sec]")]; let best = 0; secs.forEach((el, i) => { if (el.getBoundingClientRect().top < innerHeight * 0.5) best = i; }); setAct(best); };
    addEventListener("scroll", f, { passive: true }); f(); return () => removeEventListener("scroll", f);
  }, []);
  return (
    <div className="rail">{labels.map((l, i) => <button key={l} className={i === act ? "on" : ""} onClick={() => document.querySelectorAll("[data-sec]")[i]?.scrollIntoView({ behavior: "smooth" })}><span>{l}</span><i /></button>)}</div>
  );
}
