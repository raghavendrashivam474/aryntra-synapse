import { useState, useMemo } from "react";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";

interface Props {
  id: string;
  from: [number, number, number];
  to: [number, number, number];
  label: string;
  provenance: string;
  isSelected: boolean;
  onClick: () => void;
}

export default function RelationshipEdge({
  id: _id, from, to, label, provenance, isSelected, onClick,
}: Props) {
  const [hovered, setHovered] = useState(false);

  const fromVec = useMemo(() => new THREE.Vector3(...from), [from]);
  const toVec = useMemo(() => new THREE.Vector3(...to), [to]);

  const midpoint = useMemo(
    () => new THREE.Vector3().lerpVectors(fromVec, toVec, 0.5),
    [fromVec, toVec]
  );

  const arrowPos = useMemo(
    () => new THREE.Vector3().lerpVectors(fromVec, toVec, 0.72),
    [fromVec, toVec]
  );

  const arrowRotation = useMemo(() => {
    const dir = new THREE.Vector3().subVectors(toVec, fromVec).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), dir
    );
    return new THREE.Euler().setFromQuaternion(q);
  }, [fromVec, toVec]);

  const lineColor = isSelected ? "#4fc3f7" : hovered ? "#aaaacc" : "#555577";

  return (
    <group>
      {/* Relationship line */}
      <Line
        points={[from, to]}
        color={lineColor}
        lineWidth={isSelected ? 2.5 : 1}
      />

      {/* Directional arrowhead */}
      <mesh position={arrowPos} rotation={arrowRotation}>
        <coneGeometry args={[0.07, 0.22, 8]} />
        <meshBasicMaterial color={lineColor} />
      </mesh>

      {/* Invisible hitbox for clicking */}
      <mesh
        position={midpoint}
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = "auto"; }}
      >
        <sphereGeometry args={[0.25, 8, 8]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>

      {/* Label */}
      <Html
        position={[midpoint.x, midpoint.y + 0.35, midpoint.z]}
        center
        distanceFactor={8}
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        <div style={{
          color: isSelected ? "#4fc3f7" : "#8888aa",
          fontSize: "11px",
          fontFamily: "'Courier New', monospace",
          textAlign: "center",
          whiteSpace: "nowrap",
          textShadow: "0 0 4px #000",
          background: "rgba(13,13,26,0.75)",
          padding: "2px 8px",
          borderRadius: "3px",
          border: isSelected ? "1px solid #4fc3f7" : "1px solid transparent",
        }}>
          {label}
          {isSelected && (
            <div style={{ fontSize: "9px", color: "#666", marginTop: "2px" }}>
              {provenance}
            </div>
          )}
        </div>
      </Html>
    </group>
  );
}

