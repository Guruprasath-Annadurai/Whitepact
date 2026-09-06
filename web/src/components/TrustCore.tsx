// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { Suspense, useEffect, useRef, useState } from "react";
import { TextureLoader } from "three";
import type { Group } from "three";
import { publicAsset } from "../lib/assets";

const stages = ["Request", "Identity", "Authority", "Policy", "Risk", "Approval", "Decision", "Evidence"];

function CorePlane({ stage, reduced }: { stage: number; reduced: boolean }) {
  const texture = useLoader(TextureLoader, publicAsset("trust-core-head.png"));
  const group = useRef<Group>(null);

  useFrame(({ pointer, clock }) => {
    if (!group.current || reduced) return;
    group.current.rotation.y += ((pointer.x * 0.035) - group.current.rotation.y) * 0.025;
    group.current.rotation.x += ((-pointer.y * 0.018) - group.current.rotation.x) * 0.025;
    group.current.position.y = Math.sin(clock.elapsedTime * 0.38) * 0.025;
  });

  const y = [2.15, 1.55, 0.93, 0.3, -0.34, -0.98, -1.58, -2.25][stage] ?? 0;
  return (
    <group ref={group} position={[0.3, -0.05, 0]}>
      <mesh>
        <planeGeometry args={[5.05, 5.53]} />
        <meshBasicMaterial map={texture} transparent toneMapped={false} />
      </mesh>
      <mesh position={[0.12, y, 0.06]}>
        <sphereGeometry args={[0.09, 24, 24]} />
        <meshBasicMaterial color={stage === 1 || stage === 7 ? "#5ed6e6" : stage === 2 || stage === 4 ? "#f2b84b" : stage === 5 ? "#a984ef" : "#f51b2b"} />
      </mesh>
    </group>
  );
}

export function TrustCore() {
  const [stage, setStage] = useState(0);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (reduced) return;
    const onScroll = () => {
      const progress = Math.min(1, Math.max(0, window.scrollY / (window.innerHeight * 3.5)));
      setStage(Math.min(stages.length - 1, Math.floor(progress * stages.length)));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [reduced]);

  return (
    <div className="trust-core" aria-hidden="true">
      <Canvas dpr={[1, 1.5]} camera={{ position: [0, 0, 5.8], fov: 46 }} gl={{ alpha: true, antialias: true }}>
        <Suspense fallback={null}>
          <CorePlane stage={stage} reduced={reduced} />
        </Suspense>
      </Canvas>
      <div className="trust-core__stage"><span>{String(stage + 1).padStart(2, "0")}</span>{stages[stage]}</div>
    </div>
  );
}
