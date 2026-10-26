import React, { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Icosahedron, Sphere, Line, Trail, Stars, Sparkles, MeshDistortMaterial, RoundedBox, Html, PerformanceMonitor } from "@react-three/drei";
import { useState } from "react";
import { EffectComposer, Bloom, ChromaticAberration, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";

const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const AGENTS = [
  { r: 3.3, s: 0.55, ph: 0.0, c: "#ffb347", tilt: 0.25 }, { r: 4.0, s: 0.4, ph: 1.4, c: "#7fd4ff", tilt: -0.3 }, { r: 4.7, s: 0.33, ph: 2.9, c: "#9dff8a", tilt: 0.5 },
  { r: 3.8, s: 0.47, ph: 4.2, c: "#d8a8ff", tilt: -0.15 }, { r: 5.3, s: 0.27, ph: 5.4, c: "#ff8a8a", tilt: 0.1 },
];
const CAGE = new THREE.Vector3(3.6, 0.7, 0.4);
const ATTACKER_FROM = new THREE.Vector3(10, 4.5, -4), ATTACKER_TO = new THREE.Vector3(6.2, 2.4, -1);

/* shared animation state: damped scroll + shock pulse */
function Driver({ progress, sp, shock, fx }) {
  const prev = useRef(0);
  useFrame((s, d) => {
    sp.current += (progress.current - sp.current) * (1 - Math.exp(-3.2 * d));
    if (prev.current < 0.5 && sp.current >= 0.5) shock.current = s.clock.elapsedTime;     // the moment containment fires
    prev.current = sp.current;
    const age = s.clock.elapsedTime - shock.current;
    fx.current = age >= 0 && age < 2.4 ? Math.exp(-age * 2.2) : 0;
  });
  return null;
}

const NEB_V = `varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const NEB_F = `uniform float uT; uniform float uP; uniform float uS; varying vec3 vP;
float h(vec3 p){ p = fract(p * 0.3183099 + .1); p *= 17.; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float n(vec3 x){ vec3 i = floor(x), f = fract(x); f = f * f * (3. - 2. * f);
  return mix(mix(mix(h(i), h(i + vec3(1,0,0)), f.x), mix(h(i + vec3(0,1,0)), h(i + vec3(1,1,0)), f.x), f.y), mix(mix(h(i + vec3(0,0,1)), h(i + vec3(1,0,1)), f.x), mix(h(i + vec3(0,1,1)), h(i + vec3(1,1,1)), f.x), f.y), f.z); }
float fbm(vec3 p){ float a = .5, s = 0.; for(int i = 0; i < 3; i++){ s += a * n(p); p *= 2.03; a *= .5; } return s; }
void main(){ vec3 p = vP * 2.3 + vec3(0., uT * .025, uT * .018); float q = fbm(p + vec3(uT * .04, 0., uT * .03));
  vec3 c1 = vec3(.42, .02, .07), c2 = vec3(.2, .04, .42), c3 = vec3(.9, .12, .1);
  vec3 col = mix(c1, c2, smoothstep(.25, .85, q + uP * .35)); col = mix(col, c3, uS * .55 * smoothstep(.3, .9, q));
  col *= pow(q, 2.6) * 1.7; gl_FragColor = vec4(col, 1.); }`;

function Nebula({ sp, fx }) {
  const mat = useRef();
  useFrame((s) => { mat.current.uniforms.uT.value = s.clock.elapsedTime; mat.current.uniforms.uP.value = sp.current; mat.current.uniforms.uS.value = fx.current; });
  return <mesh><sphereGeometry args={[42, 20, 20]} /><shaderMaterial ref={mat} side={THREE.BackSide} depthWrite={false} toneMapped={false} vertexShader={NEB_V} fragmentShader={NEB_F} uniforms={{ uT: { value: 0 }, uP: { value: 0 }, uS: { value: 0 } }} /></mesh>;
}

function Pentagram({ sp, fx }) {
  const g = useRef(), ring = useRef();
  const pts = useMemo(() => [0, 2, 4, 1, 3, 0].map((i) => { const a = Math.PI / 2 + (i * 2 * Math.PI) / 5; return new THREE.Vector3(Math.cos(a) * 2.9, Math.sin(a) * 2.9, 0); }), []);
  useFrame((s, d) => { g.current.rotation.z += d * (0.12 + sp.current * 0.35 + fx.current * 2); const k = 1 + smooth(0.6, 0.8, sp.current) * 0.28 + fx.current * 0.35; g.current.scale.setScalar(k); ring.current.material.opacity = 0.55 + fx.current; });
  return (
    <group ref={g} rotation={[1.25, 0, 0]}>
      <Line points={pts} color="#ff3b3b" lineWidth={2.6} />
      <mesh ref={ring}><torusGeometry args={[2.95, 0.014, 12, 180]} /><meshBasicMaterial color="#ff3b3b" transparent opacity={0.6} toneMapped={false} /></mesh>
      <mesh><torusGeometry args={[3.4, 0.006, 12, 180]} /><meshBasicMaterial color="#8a1020" toneMapped={false} /></mesh>
    </group>
  );
}

/* floating 3D access token: appears beside the "every check passes" copy */
function TokenCard({ sp }) {
  const g = useRef(); const [show, setShow] = useState(false); const shown = useRef(false);
  useFrame((s) => {
    const p = sp.current, vis = smooth(0.05, 0.14, p) * (1 - smooth(0.24, 0.32, p)), t = s.clock.elapsedTime;
    const on = vis > 0.25; if (on !== shown.current) { shown.current = on; setShow(on); }
    g.current.visible = vis > 0.01; g.current.scale.setScalar(0.3 + vis * 0.7); g.current.position.set(3.7 - (1 - vis) * 3, 1.1 + Math.sin(t * 0.9) * 0.15, 1.6);
    g.current.rotation.set(Math.sin(t * 0.5) * 0.08, -0.45 + Math.sin(t * 0.7) * 0.1, 0.05);
  });
  return (
    <group ref={g} visible={false}>
      <RoundedBox args={[2.9, 1.8, 0.07]} radius={0.09} smoothness={4}><meshStandardMaterial color="#12060b" emissive="#3a0a12" emissiveIntensity={0.8} metalness={0.7} roughness={0.25} /></RoundedBox>
      <mesh position={[0, 0, 0.045]}><planeGeometry args={[2.9, 1.8]} /><meshBasicMaterial color="#ff3b3b" transparent opacity={0.06} toneMapped={false} /></mesh>
      {show && <Html transform position={[0, 0, 0.06]} distanceFactor={2.6} style={{ pointerEvents: "none" }}>
        <div className="tok3d"><b>ACCESS TOKEN · EdDSA</b>{[["signature valid", 1], ["not expired", 1], ["scope allows call", 1], ["still the same agent?", 0]].map(([l, ok]) => <div key={l} className={ok ? "ok" : "no"}><i>{ok ? "✓" : "✗"}</i>{l}</div>)}</div>
      </Html>}
    </group>
  );
}

/* thin guide orbit for the agent that will drift: it dims as the agent leaves it */
function OrbitGuide({ sp }) {
  const m = useRef();
  useFrame((s) => { const p = sp.current; m.current.material.opacity = 0.5 * (1 - smooth(0.3, 0.55, p)) * smooth(0.1, 0.2, p); m.current.rotation.z += 0.001; });
  return <mesh ref={m} rotation={[1.2, 0.3, 0]}><torusGeometry args={[3.3, 0.01, 8, 160]} /><meshBasicMaterial color="#ffb347" transparent opacity={0} toneMapped={false} /></mesh>;
}

/* six evidence-plane crystals assemble around the core in the final section */
const PLANE_SHAPES = [["P1", "Role contract", "#ff4a4a", "box"], ["P2", "Provenance", "#ff8a3c", "oct"], ["P3", "Decoys", "#e8c34a", "tet"], ["P4", "Behaviour", "#7fd4ff", "ico"], ["P5", "Delegation", "#c08bff", "dod"], ["P6", "Slow drift", "#6cc58a", "knot"]];
function PlaneCrystals({ sp }) {
  const grp = useRef(), items = useRef([]); const [show, setShow] = useState(false); const shown = useRef(false);
  useFrame((s, d) => {
    const p = sp.current, k = smooth(0.78, 0.93, p), t = s.clock.elapsedTime;
    const on = k > 0.5; if (on !== shown.current) { shown.current = on; setShow(on); }
    grp.current.visible = k > 0.01; grp.current.rotation.y += d * 0.25;
    items.current.forEach((m, i) => { if (!m) return; const a = (i / 6) * Math.PI * 2, R = 3.7 + (1 - k) * 4; m.position.set(Math.cos(a) * R, Math.sin(t * 0.8 + i) * 0.35, Math.sin(a) * R); m.scale.setScalar(k * (0.7 + Math.sin(t * 1.5 + i) * 0.04)); m.rotation.x += d * 0.5; m.rotation.y += d * 0.7; });
  });
  const geo = (t) => (t === "box" ? <boxGeometry args={[0.8, 0.8, 0.8]} /> : t === "oct" ? <octahedronGeometry args={[0.7]} /> : t === "tet" ? <tetrahedronGeometry args={[0.8]} /> : t === "ico" ? <icosahedronGeometry args={[0.7, 0]} /> : t === "dod" ? <dodecahedronGeometry args={[0.7]} /> : <torusKnotGeometry args={[0.45, 0.14, 80, 10]} />);
  return (
    <group ref={grp} visible={false}>
      {PLANE_SHAPES.map(([id, label, col, shape], i) => (
        <group key={id} ref={(m) => (items.current[i] = m)}>
          <mesh>{geo(shape)}<meshBasicMaterial color={col} wireframe toneMapped={false} /></mesh>
          <mesh scale={0.62}>{geo(shape)}<meshStandardMaterial color={col} emissive={col} emissiveIntensity={1.6} toneMapped={false} /></mesh>
          {show && <Html center distanceFactor={9} position={[0, -1.05, 0]} style={{ pointerEvents: "none" }}><div className="crystal-label" style={{ color: col }}>{id} · {label}</div></Html>}
        </group>
      ))}
    </group>
  );
}

function Gyro() {
  const a = useRef(), b = useRef(), c = useRef();
  useFrame((s, d) => { a.current.rotation.x += d * 0.6; b.current.rotation.y += d * 0.45; c.current.rotation.z += d * 0.8; });
  const ring = (r, col) => <><torusGeometry args={[r, 0.008, 8, 120]} /><meshBasicMaterial color={col} transparent opacity={0.55} toneMapped={false} /></>;
  return <group><mesh ref={a} rotation={[0.4, 0, 0]}>{ring(1.65, "#ff6a5a")}</mesh><mesh ref={b} rotation={[0, 0.5, 0.3]}>{ring(1.95, "#ff3b3b")}</mesh><mesh ref={c} rotation={[1.2, 0.2, 0]}>{ring(2.25, "#c08bff")}</mesh></group>;
}

function Core({ sp, fx }) {
  const inner = useRef(), shell = useRef(), waves = useRef([]);
  useFrame((s, d) => {
    const t = s.clock.elapsedTime; shell.current.rotation.y += d * (0.25 + fx.current * 3); shell.current.rotation.x += d * 0.1;
    inner.current.scale.setScalar(1 + Math.sin(t * 2.2) * 0.06 + fx.current * 0.5);
    waves.current.forEach((w, i) => { if (!w) return; const a = (s.__age ?? 9) - i * 0.18; const on = a > 0 && a < 2.2; w.visible = on; if (on) { w.scale.setScalar(0.5 + a * 7); w.material.opacity = (1 - a / 2.2) * 0.8; } });
  });
  return (
    <group>
      <Icosahedron ref={shell} args={[1.25, 1]}><meshBasicMaterial color="#ff4a4a" wireframe toneMapped={false} /></Icosahedron>
      <Sphere ref={inner} args={[0.62, 64, 64]}><MeshDistortMaterial color="#ff2323" emissive="#ff1a1a" emissiveIntensity={2.4} distort={0.45} speed={2.4} toneMapped={false} /></Sphere>
      {[0, 1, 2].map((i) => <mesh key={i} ref={(m) => (waves.current[i] = m)} rotation={[Math.PI / 2, 0, 0]} visible={false}><ringGeometry args={[0.96, 1, 96]} /><meshBasicMaterial color="#ff5a4a" transparent side={THREE.DoubleSide} toneMapped={false} depthWrite={false} /></mesh>)}
    </group>
  );
}

/* beam between two points as a stretched box */
function Beam({ a, b, color, opacity = 0.3, width = 0.018 }) {
  const m = useRef();
  useFrame(() => { const pa = a(), pb = b(); const mid = pa.clone().add(pb).multiplyScalar(0.5); m.current.position.copy(mid); m.current.lookAt(pb); m.current.scale.set(1, 1, pa.distanceTo(pb)); });
  return <mesh ref={m}><boxGeometry args={[width, width, 1]} /><meshBasicMaterial color={color} transparent opacity={opacity} toneMapped={false} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>;
}

function Agents({ sp, fx }) {
  const refs = useRef([]), cageRef = useRef(), pulses = useRef([]), mats = useRef([]), atk = useRef(), beam = useRef();
  const zero = useMemo(() => new THREE.Vector3(), []);
  const pos = useMemo(() => AGENTS.map(() => new THREE.Vector3()), []);
  useFrame((s) => {
    const t = s.clock.elapsedTime, p = sp.current;
    const drift = smooth(0.28, 0.6, p), contain = smooth(0.62, 0.78, p);
    AGENTS.forEach((a, i) => {
      const m = refs.current[i]; if (!m) return;
      const ang = t * a.s + a.ph; let r = a.r; if (i === 0) r += drift * 3.6 * (1 - contain);
      pos[i].set(Math.cos(ang) * r, Math.sin(ang * 0.9) * r * a.tilt * 1.6, Math.sin(ang) * r * 0.55);
      if (i === 0) pos[i].lerp(CAGE.clone().add(new THREE.Vector3(Math.sin(t * 2) * 0.06, Math.cos(t * 2.3) * 0.06, 0)), contain);
      m.position.copy(pos[i]);
      if (i === 0) {
        const col = new THREE.Color(a.c).lerp(new THREE.Color("#ff2020"), smooth(0.22, 0.46, p)); mats.current[0].color.copy(col); mats.current[0].emissive.copy(col);
        cageRef.current.visible = contain > 0.5; cageRef.current.position.copy(CAGE); cageRef.current.rotation.y = t * 0.6; cageRef.current.rotation.x = t * 0.3; cageRef.current.scale.setScalar(0.6 + contain * 0.5 + Math.sin(t * 4) * 0.03);
      }
    });
    // attacker object flies in, fires the hijack beam, then retreats when contained
    const near = smooth(0.12, 0.3, p) * (1 - smooth(0.5, 0.62, p)); atk.current.position.lerpVectors(ATTACKER_FROM, ATTACKER_TO, near); atk.current.visible = near > 0.02; atk.current.rotation.x = t; atk.current.rotation.y = t * 1.3;
    const pa = atk.current.position, pb = pos[0]; beam.current.position.copy(pa).add(pb).multiplyScalar(0.5); beam.current.lookAt(pb); beam.current.scale.set(1, 1, pa.distanceTo(pb));
    beam.current.visible = near > 0.6; beam.current.material.opacity = 0.55 + Math.sin(t * 30) * 0.3;
    pulses.current.forEach((pm, k) => { if (!pm) return; const f = (t * 0.55 + k * 0.23) % 1; pm.position.lerpVectors(pos[k % 5], zero, f); pm.scale.setScalar(0.5 + Math.sin(f * Math.PI) * 0.8); });
  });
  return (
    <group>
      {AGENTS.map((a, i) => (
        <group key={i}>
          <Trail width={i === 0 ? 1.8 : 1.1} length={8} color={a.c} attenuation={(t) => t * t}>
            <mesh ref={(m) => (refs.current[i] = m)}><sphereGeometry args={[i === 0 ? 0.2 : 0.14, 24, 24]} /><meshStandardMaterial ref={(m) => (mats.current[i] = m)} color={a.c} emissive={a.c} emissiveIntensity={2.6} toneMapped={false} /></mesh>
          </Trail>
          <Beam a={() => pos[i]} b={() => zero} color={a.c} opacity={0.16} />
        </group>
      ))}
      <mesh ref={atk} visible={false}><octahedronGeometry args={[0.38, 0]} /><meshBasicMaterial color="#ff3b3b" wireframe toneMapped={false} /></mesh>
      <mesh ref={beam} visible={false}><boxGeometry args={[0.05, 0.05, 1]} /><meshBasicMaterial color="#ff3b3b" transparent opacity={0.6} toneMapped={false} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      <mesh ref={cageRef} visible={false}><boxGeometry args={[1.1, 1.1, 1.1]} /><meshBasicMaterial color="#ff3b3b" wireframe toneMapped={false} /></mesh>
      {Array.from({ length: 10 }).map((_, k) => <mesh key={k} ref={(m) => (pulses.current[k] = m)}><sphereGeometry args={[0.045, 8, 8]} /><meshBasicMaterial color={k % 3 === 0 ? "#ff6a5a" : "#7fd4ff"} toneMapped={false} /></mesh>)}
    </group>
  );
}

function Particles({ sp }) {
  const ref = useRef();
  const geo = useMemo(() => {
    const n = 1000, a = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { const r = 5 + Math.random() * 15, th = Math.random() * 6.283, ph = Math.acos(2 * Math.random() - 1); a.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) * 0.7, r * Math.sin(ph) * Math.sin(th)], i * 3); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(a, 3)); return g;
  }, []);
  useFrame((s, d) => { ref.current.rotation.y += d * (0.02 + sp.current * 0.06); });
  return <points ref={ref} geometry={geo}><pointsMaterial size={0.035} color="#ff7a6a" transparent opacity={0.7} depthWrite={false} blending={THREE.AdditiveBlending} sizeAttenuation /></points>;
}

function Rig({ sp, fx }) {
  const target = useMemo(() => new THREE.Vector3(), []); const look = useMemo(() => new THREE.Vector3(), []);
  useFrame((s, d) => {
    const p = sp.current, t = s.clock.elapsedTime;
    const K = [[0, [0, 0.4, 10.5]], [0.3, [0.5, 1.8, 7.2]], [0.55, [4.6, 1.2, 7.8]], [0.8, [-1.5, 2.4, 6.5]], [1, [0, -0.6, 9]]];
    let i = 0; while (i < K.length - 2 && p > K[i + 1][0]) i++;
    const f = smooth(K[i][0], K[i + 1][0], p), a = K[i][1], b = K[i + 1][1];
    const sh = fx.current * 0.18;
    target.set(a[0] + (b[0] - a[0]) * f + s.pointer.x * 1.0 + Math.sin(t * 60) * sh, a[1] + (b[1] - a[1]) * f + s.pointer.y * 0.6 + Math.cos(t * 55) * sh, a[2] + (b[2] - a[2]) * f);
    s.camera.position.lerp(target, 1 - Math.pow(0.0008, d));
    look.set(smooth(0.45, 0.7, p) * 1.6 * (1 - smooth(0.78, 1, p)), 0.2, 0); s.camera.lookAt(look);
    s.camera.rotation.z += Math.sin(t * 0.4) * 0.004 + s.pointer.x * -0.01;
    s.camera.fov += ((52 + p * 4 - fx.current * 8) - s.camera.fov) * 0.1; s.camera.updateProjectionMatrix();
  });
  return null;
}

function Post({ fx, low }) {
  const bloom = useRef(), ca = useRef(); const off = useMemo(() => new THREE.Vector2(0.0009, 0.0011), []);
  useFrame(() => { if (bloom.current) bloom.current.intensity = 1.5 + fx.current * 2.4; off.set(0.0009 + fx.current * 0.011, 0.0011 + fx.current * 0.008); });
  if (low) return null;      // quality fallback: no post-processing when the GPU struggles
  return (
    <EffectComposer multisampling={0}>
      <Bloom ref={bloom} intensity={1.5} luminanceThreshold={0.18} luminanceSmoothing={0.5} mipmapBlur levels={5} />
      <ChromaticAberration offset={off} radialModulation={false} modulationOffset={0} />
    </EffectComposer>
  );
}

/* the store's `shock` counter (a real alert) fires the same shockwave as the scripted moment */
function ShockBridge({ shockProp, shock }) {
  const last = useRef(shockProp);
  useFrame((s) => { if (shockProp !== last.current) { last.current = shockProp; shock.current = s.clock.elapsedTime; } });
  return null;
}

function WaveFeed({ shock }) {      // exposes shock age to <Core> through the three state object
  useFrame((s) => { s.__age = s.clock.elapsedTime - shock.current; });
  return null;
}

export default function Hero3D({ progress, shock: shockProp = 0 }) {
  const sp = useRef(0), fx = useRef(0), shock = useRef(-99); const [low, setLow] = useState(false); const [dpr, setDpr] = useState(1);
  return (
    <div className="hero3d">
      <Canvas camera={{ position: [0, 0.4, 10.5], fov: 52 }} dpr={dpr} gl={{ antialias: false, powerPreference: "high-performance", stencil: false, depth: true }}>
        <PerformanceMonitor ms={250} iterations={6} bounds={(f) => [28, 58]} onDecline={() => { setDpr(0.75); setLow(true); }} onIncline={() => { setDpr(1); setLow(false); }} />
        <color attach="background" args={["#06030a"]} />
        <fog attach="fog" args={["#06030a", 14, 34]} />
        <ambientLight intensity={0.35} /><pointLight position={[0, 0, 0]} intensity={30} color="#ff2a2a" distance={14} />
        <Driver progress={progress} sp={sp} shock={shock} fx={fx} /><ShockBridge shockProp={shockProp} shock={shock} /><WaveFeed shock={shock} />
        <Nebula sp={sp} fx={fx} />
        <Stars radius={60} depth={30} count={1200} factor={3} fade speed={0.6} />
        <Sparkles count={60} scale={[18, 9, 18]} size={3.2} speed={0.35} color="#ff6a5a" opacity={0.8} />
        <Particles sp={sp} /><Pentagram sp={sp} fx={fx} /><Gyro /><TokenCard sp={sp} /><OrbitGuide sp={sp} /><PlaneCrystals sp={sp} /><Core sp={sp} fx={fx} /><Agents sp={sp} fx={fx} /><Rig sp={sp} fx={fx} />
        <Post fx={fx} low={low} />
      </Canvas>
    </div>
  );
}
