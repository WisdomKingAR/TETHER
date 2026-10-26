import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, Icosahedron, Sphere, Line, OrbitControls, Stars, MeshDistortMaterial, PerformanceMonitor } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import { LEVEL_COLORS } from "../api.js";

const POS = { procurement: [-2.7, 1.2, 0.2], pricing: [-4.1, -0.3, 1.0], hr_help: [2.9, 1.6, -0.6], code_review: [3.8, -1.3, 0.6], finance_recon: [0.2, -2.9, 1.0] };
const extra = {};
const posOf = (id) => {
  if (POS[id]) return POS[id];
  if (!extra[id]) { const k = Object.keys(extra).length; const a = 0.6 + k * 1.25; extra[id] = [Math.cos(a) * 5.4, Math.sin(k * 1.7) * 1.6, Math.sin(a) * 3.2]; }
  return extra[id];
};
const v = (id) => new THREE.Vector3(...posOf(id));

function AgentNode({ a, selected, onSelect }) {
  const g = useRef(), cage = useRef(), ring = useRef(), core = useRef();
  const col = a.level >= 1 ? LEVEL_COLORS[a.level] : a.color;
  const size = 0.26 + Math.min(a.risk, 100) * 0.0035;
  useFrame((s, d) => {
    const t = s.clock.elapsedTime;
    const P = posOf(a.id); g.current.position.y = P[1] + Math.sin(t * 0.8 + P[0]) * 0.12;
    if (cage.current) { cage.current.rotation.y += d * 0.9; cage.current.rotation.x += d * 0.5; }
    ring.current.rotation.z += d * (0.4 + a.risk * 0.02); ring.current.rotation.x = 1.1;
    const target = a.level >= 3 ? 1 + Math.sin(t * 7) * 0.08 : 1; core.current.scale.lerp(new THREE.Vector3(target, target, target), 0.2);
  });
  return (
    <group ref={g} position={posOf(a.id)} onClick={(e) => { e.stopPropagation(); onSelect(a.id); }} onPointerOver={() => (document.body.style.cursor = "pointer")} onPointerOut={() => (document.body.style.cursor = "")}>
      <Sphere ref={core} args={[size, 32, 32]}><meshStandardMaterial color={col} emissive={col} emissiveIntensity={a.level >= 3 ? 3 : 1.8} toneMapped={false} /></Sphere>
      <mesh ref={ring}><torusGeometry args={[size + 0.18, 0.012, 8, 64]} /><meshBasicMaterial color={col} toneMapped={false} /></mesh>
      {selected && <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[size + 0.42, 0.02, 8, 64]} /><meshBasicMaterial color="#fff" toneMapped={false} /></mesh>}
      {a.level >= 3 && <mesh ref={cage}><boxGeometry args={[size * 3, size * 3, size * 3]} /><meshBasicMaterial color={a.level === 4 ? "#9b1c4a" : "#ff3b3b"} wireframe toneMapped={false} /></mesh>}
      <Html center distanceFactor={9} position={[0, -size - 0.55, 0]} style={{ pointerEvents: "none" }}>
        <div style={{ textAlign: "center", fontFamily: "JetBrains Mono", fontSize: 11, color: "#f4e9dc", whiteSpace: "nowrap", textShadow: "0 0 8px #000, 0 0 3px #000" }}>
          <div style={{ fontWeight: 700 }}>{a.display}{a.cold ? " · day-0" : ""}</div>
          <div style={{ color: col }}>Tier {a.level} · D {Math.round(a.risk)}{a.taint ? " · T2" : ""}</div>
        </div>
      </Html>
    </group>
  );
}

function Pulses({ pulses }) {
  const pool = useRef([]), seen = useRef(new Set()), live = useRef([]);
  useEffect(() => {
    pulses.forEach((p) => { if (!seen.current.has(p.id)) { seen.current.add(p.id); live.current.push({ ...p, t0: performance.now() }); } });
    if (seen.current.size > 400) seen.current = new Set([...seen.current].slice(-100));
  }, [pulses]);
  const core = useMemo(() => new THREE.Vector3(0, 0, 0), []);
  useFrame(() => {
    const now = performance.now(); live.current = live.current.filter((p) => now - p.t0 < 1100);
    pool.current.forEach((m, i) => {
      const p = live.current[i];
      if (!p) { m.visible = false; return; }
      const f = (now - p.t0) / 1100; m.visible = true; m.position.lerpVectors(v(p.agent), core, f);
      m.material.color.set(p.bad ? "#ff3b3b" : "#7fd4ff"); m.scale.setScalar((p.bad ? 1.9 : 1) * (0.6 + Math.sin(f * Math.PI)));
    });
  });
  return <>{Array.from({ length: 14 }).map((_, i) => <mesh key={i} ref={(m) => (pool.current[i] = m)} visible={false}><sphereGeometry args={[0.06, 10, 10]} /><meshBasicMaterial toneMapped={false} /></mesh>)}</>;
}

function Core({ alarm }) {
  const shell = useRef(); const mat = useRef();
  useFrame((s, d) => { shell.current.rotation.y += d * 0.3; shell.current.rotation.z += d * 0.12; });
  return (
    <group>
      <Icosahedron ref={shell} args={[0.95, 1]}><meshBasicMaterial color={alarm ? "#ff3b3b" : "#ff7a6a"} wireframe toneMapped={false} /></Icosahedron>
      <Sphere args={[0.42, 48, 48]}><MeshDistortMaterial ref={mat} color="#ff2a2a" emissive="#ff1a1a" emissiveIntensity={alarm ? 3.2 : 1.8} distort={alarm ? 0.65 : 0.35} speed={alarm ? 5 : 2} toneMapped={false} /></Sphere>
      <Html center distanceFactor={9} position={[0, -1.35, 0]} style={{ pointerEvents: "none" }}><div style={{ fontFamily: "Cinzel", letterSpacing: "0.3em", fontSize: 11, color: "#ff8a7a" }}>GATEWAY</div></Html>
    </group>
  );
}

function Edges({ agents }) {
  const items = Object.values(agents);
  return (
    <>
      {items.map((a) => <Line key={a.id} points={[v(a.id), new THREE.Vector3(0, 0, 0)]} color={a.level >= 3 ? "#ff3b3b" : "#5a2a30"} lineWidth={a.level >= 3 ? 1.6 : 0.8} dashed={a.level >= 3} dashSize={0.15} gapSize={0.1} transparent opacity={0.8} />)}
      {items.filter((a) => a.parent).map((a) => <Line key={"d" + a.id} points={[v(a.parent), v(a.id)]} color="#c08bff" lineWidth={1.6} />)}
    </>
  );
}

function Constellation3DInner({ agents, order, selected, onSelect, pulses, height = 520 }) {
  const [low, setLow] = useState(false);
  const list = order.map((id) => agents[id]).filter(Boolean);
  const alarm = list.some((a) => a.level >= 3);
  return (
    <div style={{ height, borderRadius: 12, overflow: "hidden", position: "relative", background: "radial-gradient(circle at 50% 45%, #1a0810, #07040a 70%)" }}>
      <Canvas camera={{ position: [0, 1.5, 10.5], fov: 48 }} dpr={low ? 0.8 : 1} gl={{ antialias: !low, powerPreference: "high-performance" }}>
        <PerformanceMonitor ms={250} iterations={6} bounds={() => [26, 58]} onDecline={() => setLow(true)} onIncline={() => setLow(false)} />
        <fog attach="fog" args={["#07040a", 10, 24]} />
        <ambientLight intensity={0.4} /><pointLight position={[0, 0, 0]} intensity={18} color="#ff2a2a" distance={12} />
        <Stars radius={40} depth={20} count={600} factor={2.5} fade speed={0.5} />
        <Core alarm={alarm} /><Edges agents={agents} />
        {list.map((a) => <AgentNode key={a.id} a={a} selected={selected === a.id} onSelect={onSelect} />)}
        <Pulses pulses={pulses} />
        <OrbitControls enablePan={false} autoRotate autoRotateSpeed={0.45} minDistance={6} maxDistance={13} maxPolarAngle={Math.PI * 0.7} minPolarAngle={Math.PI * 0.25} enableDamping />
        {!low && <EffectComposer multisampling={0}><Bloom intensity={1.2} luminanceThreshold={0.22} mipmapBlur levels={5} /></EffectComposer>}
      </Canvas>
      <div style={{ position: "absolute", left: 14, bottom: 10, fontFamily: "JetBrains Mono", fontSize: 11, color: "#a8968c" }}>drag to orbit · click an agent · violet = delegation · cage = quarantine</div>
    </div>
  );
}

// the 3D map only needs to re-render when the visible agent state actually changes
export default React.memo(Constellation3DInner, (a, b) => a.agents === b.agents && a.selected === b.selected && a.pulses === b.pulses && a.order === b.order);
