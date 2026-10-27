import { useRef, useState } from "react";
import { Html } from "@react-three/drei";
import type { Mesh } from "three";

export interface EntityVisualState {
  status: "current" | "superseded";
  selected: boolean;
  rejected: boolean;
  perspective: string;
}

interface Props {
  id: string;
  position: [number, number, number];
  visualState: EntityVisualState;
  onClick: () => void;
}

export default function EntityNode({ id, position, visualState, onClick }: Props) {
  const meshRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const baseColor = visualState.status === "current" ? "#66bb6a" : "#ef5350";
  const opacity = visualState.rejected ? 0.25 : 1.0;
  const scale = hovered ? 1.15 : 1.0;
  const emissiveIntensity = visualState.selected ? 0.5 : 0.05;

  return (
    <group position={position}>
      {/* Main sphere */}
      <mesh
        ref={meshRef}
        scale={scale}
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = "auto"; }}
      >
        <sphereGeometry args={[0.4, 32, 32]} />
        <meshStandardMaterial
          color={baseColor}
          transparent
          opacity={opacity}
          emissive={baseColor}
          emissiveIntensity={emissiveIntensity}
        />
      </mesh>

      {/* Selection ring — solid for selected */}
      {visualState.selected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.6, 0.035, 16, 64]} />
          <meshBasicMaterial color="#4fc3f7" transparent opacity={0.85} />
        </mesh>
      )}

      {/* Rejection ring — dashed appearance via segmented torus */}
      {visualState.rejected && !visualState.selected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.55, 0.02, 8, 16]} />
          <meshBasicMaterial color="#ef5350" transparent opacity={0.35} wireframe />
        </mesh>
      )}

      {/* Status marker shape: octahedron for current, box for superseded */}
      <mesh position={[0, 0.65, 0]} scale={0.1}>
        {visualState.status === "current" ? (
          <octahedronGeometry args={[1, 0]} />
        ) : (
          <boxGeometry args={[1, 1, 1]} />
        )}
        <meshBasicMaterial color={baseColor} transparent opacity={0.7} />
      </mesh>

      {/* HTML label */}
      <Html center distanceFactor={8} style={{ pointerEvents: "none", userSelect: "none" }}>
        <div style={{
          color: "#e0e0e0",
          fontSize: "12px",
          fontFamily: "'Courier New', monospace",
          textAlign: "center",
          whiteSpace: "nowrap",
          textShadow: "0 0 6px #000, 0 0 2px #000",
        }}>
          <div style={{ fontWeight: "bold", fontSize: "13px" }}>{id}</div>
          <div style={{
            fontSize: "10px",
            color: visualState.status === "current" ? "#66bb6a" : "#ef5350",
            letterSpacing: "0.1em",
          }}>
            {visualState.status === "current" ? "▲ CURRENT" : "■ SUPERSEDED"}
          </div>
          {visualState.selected && (
            <div style={{ color: "#4fc3f7", fontSize: "10px", marginTop: "2px" }}>
              ● SELECTED
            </div>
          )}
          {visualState.rejected && (
            <div style={{ color: "#ef5350", fontSize: "10px", marginTop: "2px" }}>
              ✕ REJECTED
            </div>
          )}
        </div>
      </Html>
    </group>
  );
}
