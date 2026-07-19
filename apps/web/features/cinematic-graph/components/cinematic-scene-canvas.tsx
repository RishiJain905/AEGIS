'use client';

import { Billboard, Html, Line, OrbitControls } from '@react-three/drei';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentRef } from 'react';
import * as THREE from 'three';

type OrbitControlsImpl = NonNullable<ComponentRef<typeof OrbitControls>>;
type LineImpl = NonNullable<ComponentRef<typeof Line>>;
/** Structural view of drei/three-stdlib LineMaterial without importing it. */
type DashedLineMaterial = THREE.Material & { dashOffset: number; opacity: number };

import {
  getGraphAnimationTime,
  NO_PULSE,
} from '@/features/operational-graph/semantic/edge-activity';
import type { EdgeFlowProfile } from '@/features/operational-graph/semantic/graph-semantic-styles';

import type { SceneEdge, SceneNode } from '../contracts';
import type { CameraBookmark3D } from '../contracts/camera-bookmark-3d';
import { RenderQualityTier, type RenderQualityTierValue } from '../contracts/render-quality-tier';
import { dprForTier } from '../lib/capability';
import { getGlyphTexture } from '../lib/glyph-textures';
import { applyInstancedNodeAttributes, nodeRadius } from '../lib/instanced-node-attributes';
import {
  getSceneFrameloop,
  getSceneQualityProfile,
  type SceneQualityProfile,
} from '../lib/scene-quality';
import { resolveThreeColor } from '../lib/three-color';
import { RISK_HALO_FRAGMENT, RISK_HALO_VERTEX } from '../shaders/risk-halo';

/**
 * §7.1 per-instance emissive tint: three's standard/physical materials only
 * support a uniform emissive, so we inject a per-instance emissive attribute
 * (local, reviewed GLSL snippets — no remote shader loading). The attribute is
 * uploaded only when the node set changes; nothing per-frame.
 */
function injectInstanceEmissive(shader: { vertexShader: string; fragmentShader: string }): void {
  shader.vertexShader = shader.vertexShader
    .replace(
      '#include <common>',
      '#include <common>\nattribute vec3 instanceEmissive;\nvarying vec3 vAegisEmissive;',
    )
    .replace(
      '#include <begin_vertex>',
      '#include <begin_vertex>\nvAegisEmissive = instanceEmissive;',
    );
  shader.fragmentShader = shader.fragmentShader
    .replace('#include <common>', '#include <common>\nvarying vec3 vAegisEmissive;')
    .replace(
      'vec3 totalEmissiveRadiance = emissive;',
      'vec3 totalEmissiveRadiance = vAegisEmissive;',
    );
}

const instanceEmissiveCacheKey = () => 'aegis-instance-emissive';

function InstancedNodes({
  nodes,
  profile,
  onSelect,
  onHover,
}: {
  nodes: SceneNode[];
  profile: SceneQualityProfile;
  onSelect: (nodeId: string) => void;
  onHover: (nodeId: string | null) => void;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const colorCoatRef = useRef<THREE.InstancedMesh>(null);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) {
      return;
    }
    applyInstancedNodeAttributes(mesh, colorCoatRef.current, nodes);
  }, [nodes]);

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
        onPointerOver={(event) => {
          event.stopPropagation();
          const index = event.instanceId;
          if (typeof index === 'number' && nodes[index]) {
            onHover(nodes[index].id);
          }
        }}
        onPointerOut={() => {
          onHover(null);
        }}
      >
        <icosahedronGeometry
          args={[1, profile.nodeSegments >= 20 ? 3 : profile.nodeSegments >= 14 ? 2 : 1]}
        />
        {/* No `vertexColors` on these materials: per-instance tinting rides on
            setColorAt()'s instanceColor (USE_INSTANCING_COLOR). `vertexColors`
            additionally defines USE_COLOR, whose per-vertex `color` attribute
            this geometry never provides — the unbound attribute reads
            (0, 0, 0) on ANGLE and multiplies every instance color to black. */}
        {profile.material === 'physical' ? (
          <meshPhysicalMaterial
            roughness={0.36}
            metalness={0.18}
            clearcoat={0.68}
            clearcoatRoughness={0.3}
            onBeforeCompile={injectInstanceEmissive}
            customProgramCacheKey={instanceEmissiveCacheKey}
          />
        ) : (
          <meshStandardMaterial
            roughness={0.48}
            metalness={0.12}
            onBeforeCompile={injectInstanceEmissive}
            customProgramCacheKey={instanceEmissiveCacheKey}
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

/** §7.2 billboard type glyphs: always-camera-facing sprites reusing the exact
 * 2D shape language (shared `drawShape` painter). Static — no per-frame work
 * beyond three's sprite billboarding. */
function NodeGlyphs({ nodes }: { nodes: SceneNode[] }) {
  const glyphs = useMemo(
    () =>
      nodes
        .map((node) => ({ node, texture: getGlyphTexture(node.glyphShape) }))
        .filter((entry): entry is { node: SceneNode; texture: THREE.CanvasTexture } =>
          Boolean(entry.texture),
        ),
    [nodes],
  );

  return (
    <group>
      {glyphs.map(({ node, texture }) => {
        const scale = nodeRadius(node) * 0.85;
        return (
          <sprite
            key={`glyph-${node.id}`}
            position={[node.position.x, node.position.y, node.position.z]}
            scale={[scale, scale, 1]}
            renderOrder={12}
          >
            <spriteMaterial
              map={texture}
              transparent
              opacity={node.dimmed ? 0.18 : 0.9}
              depthTest={false}
              depthWrite={false}
              toneMapped={false}
            />
          </sprite>
        );
      })}
    </group>
  );
}

interface AnimatedEdgeEntry {
  material: DashedLineMaterial;
  /** World-units-per-second dash sweep (0 when only pulse-decay applies). */
  offsetSpeed: number;
  pulseAt: number;
  baseOpacity: number;
}

/**
 * §7.4 semantic edges + §7.9 alive flow for the 3D renderer. Flow uses the
 * dash-offset uniform of the fat-line material (the spec's "dash-offset
 * shader on the edge line material") driven from the shared animation clock
 * in useFrame — scalar uniform writes only, no allocation, no rebuild.
 */
function SceneEdges({
  edges,
  nodes,
  profile,
  flowProfile,
}: {
  edges: SceneEdge[];
  nodes: SceneNode[];
  profile: SceneQualityProfile;
  flowProfile: EdgeFlowProfile;
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
        // §7.9 gating: 'full' animates every flow-capable edge; 'coarse'
        // (MEDIUM tier) only edges on the current selection/highlight;
        // 'static' (reduced motion / LOW tier) animates nothing.
        const flowAnimated =
          edge.flowSpeed > 0 &&
          flowProfile !== 'static' &&
          (flowProfile === 'full' || edge.highlighted);
        return {
          edge,
          color: resolved.color,
          opacity: edge.opacity * resolved.opacity,
          flowAnimated,
          points: [
            new THREE.Vector3(source.x, source.y, source.z),
            new THREE.Vector3(target.x, target.y, target.z),
          ] as [THREE.Vector3, THREE.Vector3],
        };
      })
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
  }, [edges, nodes, flowProfile]);

  const lineRefs = useRef(new Map<string, LineImpl>());
  const animatedRef = useRef<AnimatedEdgeEntry[]>([]);

  const registerLine = useCallback((edgeId: string, line: LineImpl | null) => {
    if (line) {
      lineRefs.current.set(edgeId, line);
    } else {
      lineRefs.current.delete(edgeId);
    }
  }, []);

  // Rebuilt only when the projection changes — the per-frame loop below walks
  // this fixed array and writes scalar uniforms.
  useEffect(() => {
    if (flowProfile === 'static') {
      animatedRef.current = [];
      return;
    }
    const entries: AnimatedEdgeEntry[] = [];
    for (const segment of segments) {
      const line = lineRefs.current.get(segment.edge.id);
      if (!line) {
        continue;
      }
      const hasPulse = segment.edge.pulseAt > NO_PULSE + 1;
      if (!segment.flowAnimated && !hasPulse) {
        continue;
      }
      entries.push({
        material: line.material as unknown as DashedLineMaterial,
        // Dash sweep in world units/sec, direction source → target.
        offsetSpeed: segment.flowAnimated
          ? segment.edge.flowSpeed * (segment.edge.highlighted ? 46 : 30)
          : 0,
        pulseAt: segment.edge.pulseAt,
        baseOpacity: segment.opacity,
      });
    }
    animatedRef.current = entries;
  }, [segments, flowProfile]);

  useFrame(() => {
    if (flowProfile === 'static' || animatedRef.current.length === 0) {
      return;
    }
    const time = getGraphAnimationTime();
    for (const entry of animatedRef.current) {
      if (entry.offsetSpeed > 0) {
        entry.material.dashOffset = -(time * entry.offsetSpeed);
      }
      if (entry.pulseAt > NO_PULSE + 1) {
        const boost = Math.exp(-Math.max(time - entry.pulseAt, 0) * 1.3);
        entry.material.opacity = Math.min(1, entry.baseOpacity + boost * 0.55);
      }
    }
  });

  return (
    <group>
      {segments.map(({ edge, color, opacity, flowAnimated, points }) => {
        // Containment (§7.4) keeps a short static dash; alive flow uses a
        // long, low-contrast travelling dash. Static profile: containment
        // stays dashed (it is semantic), flow edges render solid.
        const dashed = edge.dashed || flowAnimated;
        const dashSize = edge.dashed ? 4 : edge.highlighted ? 14 : 22;
        const gapSize = edge.dashed ? 3.5 : edge.highlighted ? 10 : 6;
        return (
          <Line
            key={edge.id}
            ref={(line: LineImpl | null) => {
              registerLine(edge.id, line);
            }}
            points={points}
            color={color}
            lineWidth={Math.max(0.75, edge.width * profile.edgeWidthScale)}
            transparent
            opacity={opacity}
            depthWrite={false}
            toneMapped={false}
            dashed={dashed}
            dashSize={dashSize}
            gapSize={gapSize}
          />
        );
      })}
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
              // §7.3: sprite-halo billboard behind the node reusing the
              // existing RISK_HALO radial-falloff shader; uColor carries the
              // §7.1 risk color, uOpacity scales with severity (critical
              // brightest — encoded in the halo token's alpha channel).
              <Billboard
                key={`risk-halo-${node.id}`}
                position={[node.position.x, node.position.y, node.position.z]}
              >
                <mesh scale={radius * (node.selected ? 3.6 : 3.1)} renderOrder={2}>
                  <planeGeometry args={[1, 1]} />
                  <shaderMaterial
                    vertexShader={RISK_HALO_VERTEX}
                    fragmentShader={RISK_HALO_FRAGMENT}
                    uniforms={{
                      uColor: { value: halo.color },
                      uOpacity: { value: Math.min(0.6, halo.opacity * 0.85) },
                    }}
                    transparent
                    depthWrite={false}
                    blending={THREE.AdditiveBlending}
                  />
                </mesh>
              </Billboard>
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
        status: resolveThreeColor(node.statusColor, '#63d6a2'),
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

/**
 * §7.5: labels stay off by default at dense zoom — the floating node card
 * (`.cinematic-node-label`, restyled per the flattened token system) appears
 * on selection or hover only, matching the 2D canvas hover/select behavior.
 * The accessible entity list below the canvas covers everything else.
 */
function SceneLabels({
  nodes,
  hoveredNodeId,
}: {
  nodes: SceneNode[];
  hoveredNodeId: string | null;
}) {
  const selected = useMemo(() => nodes.find((node) => node.selected) ?? null, [nodes]);
  const hovered = useMemo(
    () =>
      hoveredNodeId === null
        ? null
        : (nodes.find((node) => node.id === hoveredNodeId && !node.selected) ?? null),
    [hoveredNodeId, nodes],
  );

  const renderCard = (node: SceneNode, testId: string) => (
    <Html
      position={[node.position.x, node.position.y + nodeRadius(node) + 14, node.position.z]}
      center
      style={{ pointerEvents: 'none' }}
      zIndexRange={[30, 0]}
    >
      <div className="cinematic-node-label" data-testid={testId}>
        <span>{node.label}</span>
        <small>
          Risk {Math.round(node.riskScore * 100)}
          {node.status !== 'normal' ? ` · ${node.status.replaceAll('_', ' ')}` : ''}
        </small>
      </div>
    </Html>
  );

  return (
    <group>
      {selected ? renderCard(selected, 'cinematic-selected-label') : null}
      {hovered ? renderCard(hovered, 'cinematic-hover-label') : null}
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
      Math.max(...zs) - Math.min(...zs),
      600,
    );
    return {
      size: span * 2.4,
      // The ground plane sits just beneath the risk skyline's lowest node so
      // altitude reads as height-above-plan (§7.6).
      floor: Math.min(...ys) - 60,
    };
  }, [nodes]);

  return (
    <group>
      {/* Grid quieted ~35% (§7.7): ambient orientation aid, not a competing
          pattern against the risk-colored nodes it sets off. */}
      <gridHelper
        args={[
          dimensions.size,
          profile.nodeSegments >= 20 ? 42 : 28,
          resolveThreeColor('#113442').color,
          resolveThreeColor('#081b24').color,
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
  /** §7.9 flow gate resolved by the view from the capability report. */
  flowProfile: EdgeFlowProfile;
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
  flowProfile,
  onReady,
  onSelectNode,
  onBackgroundClick,
}: CinematicSceneCanvasProps) {
  const dpr = dprForTier(qualityTier, dprCap);
  const profile = getSceneQualityProfile(qualityTier);
  const frameloop = getSceneFrameloop(qualityTier, reducedMotion);
  const glRef = useRef<THREE.WebGLRenderer | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

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
        <SceneEdges edges={edges} nodes={nodes} profile={profile} flowProfile={flowProfile} />
        <RiskAndSelectionAccents nodes={nodes} profile={profile} />
        <InstancedNodes
          nodes={nodes}
          profile={profile}
          onSelect={onSelectNode}
          onHover={setHoveredNodeId}
        />
        <NodeGlyphs nodes={nodes} />
        <StatusMarkers nodes={nodes} />
        <SceneLabels nodes={nodes} hoveredNodeId={hoveredNodeId} />
      </Canvas>
      <div
        className="cinematic-canvas-vignette pointer-events-none absolute inset-0"
        aria-hidden="true"
      />
    </div>
  );
}
