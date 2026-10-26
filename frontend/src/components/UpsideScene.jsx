import React, { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Icosahedron, Sphere, Stars } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette, ChromaticAberration } from "@react-three/postprocessing";
import * as THREE from "three";

function Flip() {
  const { camera } = useThree();
  useFrame(() => { camera.up.set(0, -1, 0); camera.lookAt(0, 0, 0); });
  return null;
}

function Cage({ n }) {
  const cage = useRef(), att = useRef(), docs = useRef([]);
  useFrame((s, d) => {
    const t = s.clock.elapsedTime; cage.current.rotation.y += d * 0.4; cage.current.rotation.x = Math.sin(t * 0.4) * 0.3;
    att.current.position.set(Math.sin(t * 1.3) * 0.25, Math.cos(t * 1.7) * 0.2, 0);
    docs.current.forEach((m, i) => { if (!m) return; const a = t * 0.4 + (i / 12) * 6.283; m.position.set(Math.cos(a) * 3.1, Math.sin(a * 1.3) * 0.9, Math.sin(a) * 3.1); m.rotation.y = a; m.rotation.x = t * 0.5 + i; });
  });
  return (
    <group>
      <mesh ref={cage}><boxGeometry args={[2.1, 2.1, 2.1]} /><meshBasicMaterial color="#c08bff" wireframe toneMapped={false} /></mesh>
      <Sphere ref={att} args={[0.32, 32, 32]}><meshStandardMaterial color="#ff3b3b" emissive="#ff1a1a" emissiveIntensity={3} toneMapped={false} /></Sphere>
      <Icosahedron args={[0.9, 1]}><meshBasicMaterial color="#7fd4ff" wireframe transparent opacity={0.25} toneMapped={false} /></Icosahedron>
      {Array.from({ length: 12 }).map((_, i) => (
        <mesh key={i} ref={(m) => (docs.current[i] = m)} visible={i < Math.max(3, n)}>
          <boxGeometry args={[0.5, 0.66, 0.04]} /><meshStandardMaterial color={i % 4 === 0 ? "#ffd24a" : "#c08bff"} emissive={i % 4 === 0 ? "#ffb300" : "#7a3cff"} emissiveIntensity={1.6} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

export default function UpsideScene({ n = 3, height = 420 }) {
  return (
    <div style={{ height, borderRadius: 12, overflow: "hidden", background: "radial-gradient(circle at 50% 55%, #1b0a2a, #07040a 70%)" }}>
      <Canvas camera={{ position: [0, 0.8, 8], fov: 48 }} dpr={1} gl={{ antialias: false }}>
        <fog attach="fog" args={["#07040a", 9, 20]} /><ambientLight intensity={0.5} /><pointLight position={[0, 0, 0]} intensity={20} color="#9b5bff" distance={12} />
        <Stars radius={40} depth={20} count={1000} factor={2.5} fade speed={0.5} />
        <Flip /><Cage n={n} />
        <EffectComposer multisampling={0}><Bloom intensity={1.3} luminanceThreshold={0.2} mipmapBlur levels={5} /></EffectComposer>
      </Canvas>
    </div>
  );
}
