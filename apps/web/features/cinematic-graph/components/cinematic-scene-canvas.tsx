'use client';

import { Html, Line, OrbitControls } from '@react-three/drei';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef, type ComponentRef } from 'react';
import * as THREE from 'three';

type OrbitControlsImpl = NonNullable<ComponentRef<typeof OrbitControls>>;

import type { SceneEdge, SceneNode } from '../contracts';
import type { CameraBookmark3D } from '../contracts/camera-bookmark-3d';
import { RenderQualityTier, type RenderQualityTierValue } from '../contracts/render-quality-tier';
import { dprForTier } from '../lib/capability';
import {
  getSceneFrameloop,
  getSceneQualityProfile,
  type SceneQualityProfile,
} from '../lib/scene-quality';
import { resolveThreeColor } from '../lib/three-color';

function nodeRadius(node: SceneNode): number {
  return Math.max(9, node.size * 1.05) * (node.selected ? 1.12 : 1);
}

function InstancedNodes({
  nodes,
  profile,
  onSelect,
}: {
  nodes: SceneNode[];
  profile: SceneQualityProfile;
  onSelect: (nodeId: string) => void;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const colorCoatRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const scratchColor = useMemo(() => new THREE.Color(), []);
  const nodeColors = useMemo(
    () => nodes.map((node) => resolveThreeColor(node.color).color),
    [nodes],
  );

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) {
      return;
    }
    const colorCoat = colorCoatRef.current;

    nodes.forEach((node, index) => {
      const radius = nodeRadius(node);
      dummy.position.set(node.position.x, node.position.y, node.position.z);
      dummy.scale.setScalar(node.dimmed ? radius * 0.72 : radius);
      dummy.updateMatrix();
      mesh.setMatrixAt(index, dummy.matrix);

      scratchColor.copy(nodeColors[index] ?? resolveThreeColor('#64748b').color);
      if (node.dimmed) {
        scratchColor.multiplyScalar(0.28);
      } else if (node.highlighted || node.selected) {
        scratchColor.offsetHSL(0, 0.08, 0.08);
      }
      mesh.setColorAt(index, scratchColor);

      if (colorCoat) {
        dummy.scale.setScalar((node.dimmed ? radius * 0.72 : radius) * 1.012);
        dummy.updateMatrix();
        colorCoat.setMatrixAt(index, dummy.matrix);
        colorCoat.setColorAt(index, scratchColor);
      }
    });

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) {
      mesh.instanceColor.needsUpdate = true;
    }
    if (colorCoat) {
      colorCoat.instanceMatrix.needsUpdate = true;
      if (colorCoat.instanceColor) {
        colorCoat.instanceColor.needsUpdate = true;
      }
    }
  }, [dummy, nodeColors, nodes, scratchColor]);

  return (
    <group>
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, Math.max(nodes.length, 1)]}
        castShadow={profile.shadows}
        receiveShadow={profile.shadows}
        onClick={(event) => {
          event.stopPropagation();
          const index = event.instanceId;
          if (typeof index === 'number' && nodes[index]) {
            onSelect(nodes[index].id);
          }
        }}
      >
        <icosahedronGeometry
          args={[1, profile.nodeSegments >= 20 ? 3 : profile.nodeSegments >= 14 ? 2 : 1]}
        />
        {profile.material === 'physical' ? (
          <meshPhysicalMaterial
            vertexColors
            roughness={0.36}
            metalness={0.18}
            clearcoat={0.68}
            clearcoatRoughness={0.3}
            emissive="#167d9c"
            emissiveIntensity={0.62}
          />
        ) : (
          <meshStandardMaterial
            vertexColors
            roughness={0.48}
            metalness={0.12}
            emissive="#12627b"
            emissiveIntensity={0.52}
          />
        )}
      </instancedMesh>
      {profile.glow ? (
        <instancedMesh
          ref={colorCoatRef}
          args={[undefined, undefined, Math.max(nodes.length, 1)]}
          raycast={() => undefined}
        >
          <icosahedronGeometry
            args={[1, profile.nodeSegments >= 20 ? 3 : profile.nodeSegments >= 14 ? 2 : 1]}
          />
          <meshBasicMaterial
            vertexColors
            transparent
            opacity={0.24}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </instancedMesh>
      ) : null}
    </group>
  );
}

function SceneEdges({
  edges,
  nodes,
  profile,
}: {
  edges: SceneEdge[];
  nodes: SceneNode[];
  profile: SceneQualityProfile;
}) {
  const segments = useMemo(() => {
    const byId = new Map(nodes.map((node) => [node.id, node.position]));
    return edges
      .map((edge) => {
        const source = byId.get(edge.sourceId);
        const target = byId.get(edge.targetId);
        if (!source || !target) {
          return null;
        }
        const resolved = resolveThreeColor(edge.color, '#94a3b8');
        return {
          edge,
          color: resolved.color,
          opacity: edge.opacity * resolved.opacity,
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
      {segments.map(({ edge, color, opacity, points }) => (
        <Line
          key={edge.id}
          points={points}
          color={color}
          lineWidth={Math.max(0.75, edge.width * profile.edgeWidthScale)}
          transparent
          opacity={opacity}
          depthWrite={false}
          toneMapped={false}
        />
      ))}
    </group>
  );
}

function RiskAndSelectionAccents({
  nodes,
  profile,
}: {
  nodes: SceneNode[];
  profile: SceneQualityProfile;
}) {
  const accents = useMemo(
    () =>
      nodes.map((node) => ({
        node,
        radius: nodeRadius(node),
        halo: resolveThreeColor(node.riskHaloColor, '#38bdf8'),
      })),
    [nodes],
  );

  return (
    <group>
      {profile.glow
        ? accents
            .filter(({ halo }) => halo.opacity > 0)
            .map(({ node, radius, halo }) => (
              <mesh
                key={`risk-halo-${node.id}`}
                position={[node.position.x, node.position.y, node.position.z]}
                scale={radius * (node.selected ? 1.7 : 1.52)}
              >
                <sphereGeometry args={[1, profile.nodeSegments, profile.nodeSegments]} />
                <meshBasicMaterial
                  color={halo.color}
                  transparent
                  opacity={Math.min(0.3, 0.09 + halo.opacity * 0.3)}
                  blending={THREE.AdditiveBlending}
                  depthWrite={false}
                  side={THREE.BackSide}
                  toneMapped={false}
                />
              </mesh>
            ))
        : null}

      {accents
        .filter(({ node }) => node.selected || node.highlighted)
        .map(({ node, radius }) => (
          <group
            key={`selection-${node.id}`}
            position={[node.position.x, node.position.y, node.position.z]}
          >
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <torusGeometry args={[radius * 1.42, Math.max(0.65, radius * 0.07), 8, 40]} />
              <meshBasicMaterial
                color={
                  node.selected
                    ? resolveThreeColor('#9ce7ff').color
                    : resolveThreeColor('#fbbf24').color
                }
                transparent
                opacity={node.selected ? 0.95 : 0.72}
                depthWrite={false}
                toneMapped={false}
              />
            </mesh>
          </group>
        ))}
    </group>
  );
}

function StatusMarkers({ nodes }: { nodes: SceneNode[] }) {
  const markers = useMemo(
    () =>
      nodes.map((node) => ({
        node,
        radius: nodeRadius(node),
        status: resolveThreeColor(node.statusColor, '#22c55e'),
      })),
    [nodes],
  );

  return (
    <group>
      {markers
        .filter(({ status }) => status.opacity > 0)
        .map(({ node, radius, status }) => (
          <mesh
            key={`status-${node.id}`}
            position={[node.position.x, node.position.y + radius + 3.5, node.position.z]}
          >
            <octahedronGeometry args={[2.2, 1]} />
            <meshBasicMaterial color={status.color} toneMapped={false} />
          </mesh>
        ))}
      {markers
        .filter(({ node }) => node.evidenceMarked || node.incidentMarked)
        .map(({ node, radius }) => (
          <mesh
            key={`marker-${node.id}`}
            position={[node.position.x, node.position.y - radius - 3.5, node.position.z]}
            rotation={[0, 0, Math.PI / 4]}
          >
            <boxGeometry args={[3.4, 3.4, 3.4]} />
            <meshBasicMaterial
              color={resolveThreeColor(node.incidentMarked ? '#fb5b65' : '#fbbf24').color}
              transparent
              opacity={0.95}
              toneMapped={false}
            />
          </mesh>
        ))}
    </group>
  );
}

const MAX_SECONDARY_LABELS = 7;

/**
 * Legible labels with LOD by importance rather than raw distance: the selected
 * node always gets the full label card; highlighted and the highest-risk
 * undimmed nodes get compact tags. Everything else stays unlabeled to keep the
 * scene readable — the accessible entity list below the canvas covers the rest.
 */
function SceneLabels({ nodes }: { nodes: SceneNode[] }) {
  const labelled = useMemo(() => {
    const selected = nodes.find((node) => node.selected) ?? null;
    const secondary = nodes
      .filter((node) => !node.selected && !node.dimmed)
      .sort(
        (a, b) =>
          Number(b.highlighted) - Number(a.highlighted) ||
          b.riskScore - a.riskScore ||
          b.criticality - a.criticality,
      )
      .slice(0, MAX_SECONDARY_LABELS);
    return { selected, secondary };
  }, [nodes]);

  return (
    <group>
      {labelled.selected ? (
        <Html
          position={[
            labelled.selected.position.x,
            labelled.selected.position.y + nodeRadius(labelled.selected) + 14,
            labelled.selected.position.z,
          ]}
          center
          style={{ pointerEvents: 'none' }}
        >
          <div className="cinematic-node-label" data-testid="cinematic-selected-label">
            <span>{labelled.selected.label}</span>
            <small>Risk {Math.round(labelled.selected.riskScore * 100)}</small>
          </div>
        </Html>
      ) : null}
      {labelled.secondary.map((node) => (
        <Html
          key={`label-${node.id}`}
          position={[node.position.x, node.position.y + nodeRadius(node) + 9, node.position.z]}
          center
          style={{ pointerEvents: 'none' }}
          zIndexRange={[20, 0]}
        >
          <div className="cinematic-node-tag" data-testid={`cinematic-node-tag-${node.id}`}>
            {node.label}
          </div>
        </Html>
      ))}
    </group>
  );
}

interface CameraFlight {
  fromPosition: THREE.Vector3;
  fromTarget: THREE.Vector3;
  toPosition: THREE.Vector3;
  toTarget: THREE.Vector3;
  elapsed: number;
}

const CAMERA_FLIGHT_SECONDS = 0.65;

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Single owner of the camera pose. Bookmarks are applied by moving BOTH the
 * camera position and the OrbitControls target through the controls instance,
 * then calling controls.update() — never a bare camera.lookAt(), which would
 * fight OrbitControls' own per-frame update and fling the scene off-screen.
 */
function CameraController({
  bookmark,
  reducedMotion,
}: {
  bookmark: CameraBookmark3D;
  reducedMotion: boolean;
}) {
  const { camera, invalidate } = useThree();
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const flightRef = useRef<CameraFlight | null>(null);

  useEffect(() => {
    const controls = controlsRef.current;
    const toPosition = new THREE.Vector3(
      bookmark.position.x,
      bookmark.position.y,
      bookmark.position.z,
    );
    const toTarget = new THREE.Vector3(bookmark.target.x, bookmark.target.y, bookmark.target.z);

    if ('fov' in camera) {
      const perspective = camera as THREE.PerspectiveCamera;
      if (perspective.fov !== bookmark.fov) {
        perspective.fov = bookmark.fov;
        perspective.updateProjectionMatrix();
      }
    }

    if (reducedMotion || !controls) {
      camera.position.copy(toPosition);
      if (controls) {
        controls.target.copy(toTarget);
        controls.update();
      } else {
        camera.lookAt(toTarget);
      }
      flightRef.current = null;
    } else {
      flightRef.current = {
        fromPosition: camera.position.clone(),
        fromTarget: controls.target.clone(),
        toPosition,
        toTarget,
        elapsed: 0,
      };
    }
    invalidate();
  }, [bookmark, camera, invalidate, reducedMotion]);

  // Operator input cancels any in-progress flight instead of fighting it.
  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) {
      return;
    }
    const cancelFlight = () => {
      flightRef.current = null;
    };
    controls.addEventListener('start', cancelFlight);
    return () => {
      controls.removeEventListener('start', cancelFlight);
    };
  }, [bookmark]);

  useFrame((_, delta) => {
    const flight = flightRef.current;
    const controls = controlsRef.current;
    if (!flight || !controls) {
      return;
    }

    flight.elapsed = Math.min(CAMERA_FLIGHT_SECONDS, flight.elapsed + Math.min(delta, 0.05));
    const k = easeOutCubic(flight.elapsed / CAMERA_FLIGHT_SECONDS);
    camera.position.lerpVectors(flight.fromPosition, flight.toPosition, k);
    controls.target.lerpVectors(flight.fromTarget, flight.toTarget, k);
    controls.update();

    if (flight.elapsed >= CAMERA_FLIGHT_SECONDS) {
      flightRef.current = null;
    }
    invalidate();
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping={!reducedMotion}
      dampingFactor={0.075}
      enablePan
      enableRotate
      enableZoom
      minDistance={45}
      maxDistance={7_500}
      makeDefault
    />
  );
}

function SceneAtmosphere({ nodes, profile }: { nodes: SceneNode[]; profile: SceneQualityProfile }) {
  const dimensions = useMemo(() => {
    if (nodes.length === 0) {
      return { size: 1_200, floor: -240 };
    }
    const xs = nodes.map((node) => node.position.x);
    const ys = nodes.map((node) => node.position.y);
    const zs = nodes.map((node) => node.position.z);
    const span = Math.max(
      Math.max(...xs) - Math.min(...xs),
      Math.max(...ys) - Math.min(...ys),
      Math.max(...zs) - Math.min(...zs),
      600,
    );
    return {
      size: span * 2.4,
      floor: Math.min(...ys) - 110,
    };
  }, [nodes]);

  return (
    <group>
      <gridHelper
        args={[
          dimensions.size,
          profile.nodeSegments >= 20 ? 42 : 28,
          resolveThreeColor('#174c61').color,
          resolveThreeColor('#0b2532').color,
        ]}
        position={[0, dimensions.floor, 0]}
      />
      <mesh
        position={[0, dimensions.floor - 2, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow={profile.shadows}
      >
        <planeGeometry args={[dimensions.size, dimensions.size]} />
        <meshStandardMaterial
          color={resolveThreeColor('#061018').color}
          roughness={0.9}
          metalness={0.05}
          transparent
          opacity={0.72}
        />
      </mesh>
    </group>
  );
}

export interface CinematicSceneCanvasProps {
  nodes: SceneNode[];
  edges: SceneEdge[];
  camera: CameraBookmark3D;
  qualityTier: RenderQualityTierValue;
  dprCap: number;
  reducedMotion: boolean;
  onReady: () => void;
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
  onReady,
  onSelectNode,
  onBackgroundClick,
}: CinematicSceneCanvasProps) {
  const dpr = dprForTier(qualityTier, dprCap);
  const profile = getSceneQualityProfile(qualityTier);
  const frameloop = getSceneFrameloop(qualityTier, reducedMotion);
  const glRef = useRef<THREE.WebGLRenderer | null>(null);

  // Releasing the GL context explicitly on unmount stops Chromium from
  // recycling the orphaned GPU tiles into the page compositor, which showed up
  // as full-page tiling corruption when switching from 3D back to 2D.
  useEffect(() => {
    return () => {
      try {
        glRef.current?.forceContextLoss();
      } catch {
        // Context may already be lost; nothing to clean up.
      }
      glRef.current = null;
    };
  }, []);

  return (
    <div
      className="cinematic-canvas-shell relative h-full min-h-[22rem] w-full overflow-hidden"
      data-testid="cinematic-graph-canvas"
      role="img"
      aria-label="Three.js semantic graph canvas"
    >
      <Canvas
        dpr={dpr}
        frameloop={frameloop}
        shadows={profile.shadows}
        camera={{
          position: [camera.position.x, camera.position.y, camera.position.z],
          fov: camera.fov,
          near: 0.1,
          far: 12_000,
        }}
        gl={{
          antialias: qualityTier === RenderQualityTier.HIGH,
          alpha: false,
          powerPreference: qualityTier === RenderQualityTier.HIGH ? 'high-performance' : 'default',
        }}
        onPointerMissed={onBackgroundClick}
        onCreated={({ gl }) => {
          glRef.current = gl;
          gl.outputColorSpace = THREE.SRGBColorSpace;
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = qualityTier === RenderQualityTier.HIGH ? 1.18 : 1.05;
          gl.shadowMap.enabled = profile.shadows;
          gl.shadowMap.type = THREE.PCFSoftShadowMap;
          gl.setClearColor(0x050a10, 1);
          onReady();
        }}
      >
        <color attach="background" args={[resolveThreeColor('#050a10').color]} />
        <fog
          attach="fog"
          args={[resolveThreeColor('#07111a').color, profile.fogNear, profile.fogFar]}
        />
        <ambientLight intensity={0.46} />
        <hemisphereLight args={[0x9bdcff, 0x061018, 1.08]} />
        <directionalLight
          position={[620, 880, 540]}
          intensity={2.15}
          color={resolveThreeColor('#b9eaff').color}
          castShadow={profile.shadows}
        />
        <pointLight
          position={[-520, 180, 280]}
          intensity={48_000}
          distance={1_300}
          decay={2}
          color={resolveThreeColor('#1cb8e6').color}
        />
        <pointLight
          position={[420, -260, -360]}
          intensity={30_000}
          distance={1_100}
          decay={2}
          color={resolveThreeColor('#f59e0b').color}
        />
        <CameraController bookmark={camera} reducedMotion={reducedMotion} />
        <SceneAtmosphere nodes={nodes} profile={profile} />
        <SceneEdges edges={edges} nodes={nodes} profile={profile} />
        <RiskAndSelectionAccents nodes={nodes} profile={profile} />
        <InstancedNodes nodes={nodes} profile={profile} onSelect={onSelectNode} />
        <StatusMarkers nodes={nodes} />
        <SceneLabels nodes={nodes} />
      </Canvas>
      <div
        className="cinematic-canvas-vignette pointer-events-none absolute inset-0"
        aria-hidden="true"
      />
    </div>
  );
}
