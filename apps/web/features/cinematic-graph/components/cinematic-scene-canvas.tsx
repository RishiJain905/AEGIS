'use client';

import { useMemo } from 'react';
import { Html, Line, OrbitControls } from '@react-three/drei';
import { Canvas, useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import * as THREE from 'three';

import type { SceneEdge, SceneNode } from '../contracts';
import type { CameraBookmark3D } from '../contracts/camera-bookmark-3d';
import { RenderQualityTier, type RenderQualityTierValue } from '../contracts/render-quality-tier';
import { dprForTier } from '../lib/capability';

function parseCssColor(color: string, fallback = '#64748b'): THREE.Color {
  try {
    if (color === 'transparent' || color.length === 0) {
      return new THREE.Color(fallback);
    }
    return new THREE.Color(color.length === 9 ? color.slice(0, 7) : color);
  } catch {
    return new THREE.Color(fallback);
  }
}

function InstancedNodes({
  nodes,
  onSelect,
}: {
  nodes: SceneNode[];
  onSelect: (nodeId: string) => void;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) {
      return;
    }
    nodes.forEach((node, index) => {
      dummy.position.set(node.position.x, node.position.y, node.position.z);
      const scale = Math.max(0.4, node.size / 8) * (node.selected ? 1.35 : 1);
      dummy.scale.setScalar(node.dimmed ? scale * 0.7 : scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(index, dummy.matrix);
      color.copy(parseCssColor(node.color));
      if (node.dimmed) {
        color.multiplyScalar(0.35);
      }
      mesh.setColorAt(index, color);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) {
      mesh.instanceColor.needsUpdate = true;
    }
  }, [nodes, dummy, color]);

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, Math.max(nodes.length, 1)]}
      castShadow={false}
      receiveShadow={false}
      onClick={(event) => {
        event.stopPropagation();
        const index = event.instanceId;
        if (typeof index === 'number' && nodes[index]) {
          onSelect(nodes[index].id);
        }
      }}
    >
      <sphereGeometry args={[6, 16, 16]} />
      <meshStandardMaterial vertexColors />
    </instancedMesh>
  );
}

function SceneEdges({ edges, nodes }: { edges: SceneEdge[]; nodes: SceneNode[] }) {
  const positions = useMemo(() => {
    const byId = new Map(nodes.map((node) => [node.id, node.position]));
    return edges
      .map((edge) => {
        const source = byId.get(edge.sourceId);
        const target = byId.get(edge.targetId);
        if (!source || !target) {
          return null;
        }
        return {
          edge,
          points: [
            new THREE.Vector3(source.x, source.y, source.z),
            new THREE.Vector3(target.x, target.y, target.z),
          ] as [THREE.Vector3, THREE.Vector3],
        };
      })
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
  }, [edges, nodes]);

  return (
    <group>
      {positions.map(({ edge, points }) => (
        <Line
          key={edge.id}
          points={points}
          color={parseCssColor(edge.color, '#94a3b8')}
          lineWidth={Math.max(1, edge.width)}
          transparent
          opacity={edge.opacity}
        />
      ))}
    </group>
  );
}

function StatusMarkers({ nodes }: { nodes: SceneNode[] }) {
  return (
    <group>
      {nodes
        .filter((node) => node.statusColor !== 'transparent')
        .map((node) => (
          <mesh
            key={`status-${node.id}`}
            position={[node.position.x, node.position.y + node.size * 0.9, node.position.z]}
          >
            <sphereGeometry args={[2.2, 8, 8]} />
            <meshBasicMaterial color={parseCssColor(node.statusColor, '#22c55e')} />
          </mesh>
        ))}
      {nodes
        .filter((node) => node.evidenceMarked || node.incidentMarked)
        .map((node) => (
          <mesh
            key={`marker-${node.id}`}
            position={[node.position.x, node.position.y - node.size * 0.9, node.position.z]}
          >
            <boxGeometry args={[3, 3, 3]} />
            <meshBasicMaterial
              color={node.incidentMarked ? '#ef4444' : '#eab308'}
              transparent
              opacity={0.9}
            />
          </mesh>
        ))}
    </group>
  );
}

function SelectedLabel({ nodes }: { nodes: SceneNode[] }) {
  const selected = nodes.find((node) => node.selected);
  if (!selected) {
    return null;
  }
  return (
    <Html position={[selected.position.x, selected.position.y + 18, selected.position.z]} center>
      <div
        className="rounded bg-[var(--aegis-surface-elevated)] px-2 py-1 text-xs text-[var(--aegis-text-primary)] shadow"
        data-testid="cinematic-selected-label"
      >
        {selected.label}
      </div>
    </Html>
  );
}

function CameraController({
  camera,
  reducedMotion,
  enableControls,
}: {
  camera: CameraBookmark3D;
  reducedMotion: boolean;
  enableControls: boolean;
}) {
  const { camera: threeCamera } = useThree();
  useEffect(() => {
    threeCamera.position.set(camera.position.x, camera.position.y, camera.position.z);
    threeCamera.lookAt(camera.target.x, camera.target.y, camera.target.z);
    if ('fov' in threeCamera) {
      (threeCamera as THREE.PerspectiveCamera).fov = camera.fov;
      (threeCamera as THREE.PerspectiveCamera).updateProjectionMatrix();
    }
  }, [camera, threeCamera]);

  return (
    <OrbitControls
      enableDamping={!reducedMotion}
      enablePan={enableControls}
      enableRotate={enableControls}
      enableZoom={enableControls}
      makeDefault
      target={[camera.target.x, camera.target.y, camera.target.z]}
    />
  );
}

function VisibilityGate({ children }: { children: React.ReactNode }) {
  const { gl, invalidate } = useThree();
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        gl.setAnimationLoop(null);
      } else {
        invalidate();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      gl.setAnimationLoop(null);
    };
  }, [gl, invalidate]);
  return <>{children}</>;
}

export interface CinematicSceneCanvasProps {
  nodes: SceneNode[];
  edges: SceneEdge[];
  camera: CameraBookmark3D;
  qualityTier: RenderQualityTierValue;
  dprCap: number;
  reducedMotion: boolean;
  onSelectNode: (nodeId: string) => void;
  onBackgroundClick: () => void;
}

export function CinematicSceneCanvas({
  nodes,
  edges,
  camera,
  qualityTier,
  dprCap,
  reducedMotion,
  onSelectNode,
  onBackgroundClick,
}: CinematicSceneCanvasProps) {
  const dpr = dprForTier(qualityTier, dprCap);
  const frameloop = qualityTier === RenderQualityTier.LOW || reducedMotion ? 'demand' : 'always';

  return (
    <div
      className="h-full min-h-[16rem] w-full"
      data-testid="cinematic-graph-canvas"
      role="img"
      aria-label="Three.js semantic graph canvas"
    >
      <Canvas
        dpr={dpr}
        frameloop={frameloop}
        camera={{
          position: [camera.position.x, camera.position.y, camera.position.z],
          fov: camera.fov,
          near: 0.1,
          far: 5000,
        }}
        gl={{ antialias: qualityTier === RenderQualityTier.HIGH, powerPreference: 'default' }}
        onPointerMissed={() => {
          onBackgroundClick();
        }}
        onCreated={({ gl }) => {
          gl.setClearColor(new THREE.Color('#0b1220'));
        }}
      >
        <VisibilityGate>
          <ambientLight intensity={0.55} />
          <directionalLight position={[120, 180, 80]} intensity={0.85} />
          <CameraController
            camera={camera}
            reducedMotion={reducedMotion}
            enableControls={!reducedMotion || qualityTier !== RenderQualityTier.LOW}
          />
          <SceneEdges edges={edges} nodes={nodes} />
          <InstancedNodes nodes={nodes} onSelect={onSelectNode} />
          <StatusMarkers nodes={nodes} />
          <SelectedLabel nodes={nodes} />
          <gridHelper args={[600, 30, '#1e293b', '#122033']} position={[0, -40, 0]} />
        </VisibilityGate>
      </Canvas>
    </div>
  );
}
