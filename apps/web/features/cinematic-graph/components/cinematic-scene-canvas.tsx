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

import type { SceneEdge, SceneNode, SceneZone } from '../contracts';
import type { CameraBookmark3D } from '../contracts/camera-bookmark-3d';
import { RenderQualityTier, type RenderQualityTierValue } from '../contracts/render-quality-tier';
import { dprForTier } from '../lib/capability';
import { edgeArcKind, edgeArcPoints, type EdgeArcKind } from '../lib/edge-curves';
import {
  applyInstancedNodeAttributes,
  applyPylonAttributes,
  nodeRadius,
} from '../lib/instanced-node-attributes';
import {
  getSceneFrameloop,
  getSceneQualityProfile,
  type SceneQualityProfile,
} from '../lib/scene-quality';
import { resolveThreeColor } from '../lib/three-color';
import { getZoneLabelTexture } from '../lib/zone-label-texture';
import { RISK_HALO_FRAGMENT, RISK_HALO_VERTEX } from '../shaders/risk-halo';

/**
 * The bastion ring — AEGIS's operations theater. The org renders as a ring of
 * sector platforms floating in a void: assets are typed crystalline
 * structures anchored to their platform by light pylons, criticality reads as
 * skyline height, and cross-zone traffic arcs over the dark interior. Threat
 * state owns the light: fog-of-war assets sit dark and calm, detection
 * ignites them, containment visibly severs them.
 */

const VOID_BG = '#04060b';
const FOG_COLOR = '#070a13';

const ALERT_RIM: Record<SceneZone['alertLevel'], string> = {
  calm: '#31435e',
  guarded: '#9aa8ff',
  elevated: '#f1c257',
  critical: '#ff7078',
};

const ALERT_RIM_OPACITY: Record<SceneZone['alertLevel'], number> = {
  calm: 0.5,
  guarded: 0.85,
  elevated: 0.95,
  critical: 1,
};

const STATUS_TINTS: Record<string, string> = {
  suspicious: '#f1c257',
  under_investigation: '#68d0ee',
  contained: '#9aa8ff',
  compromised: '#ff7078',
};

/**
 * Per-instance emissive tint: three's standard/physical materials only
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

/** Stable render order for the typed structure groups. */
const GLYPH_ORDER: ReadonlyArray<SceneNode['glyphShape']> = [
  'circle',
  'square',
  'hexagon',
  'diamond',
  'triangle',
];

/** The 2D glyph language extruded into silhouettes: circle→gem, square→slab,
 * hexagon→prism, diamond→octahedron, triangle→pyramid. */
function TypedGeometry({
  shape,
  profile,
}: {
  shape: SceneNode['glyphShape'];
  profile: SceneQualityProfile;
}) {
  const detail = profile.nodeSegments >= 20 ? 2 : 1;
  switch (shape) {
    case 'square':
      return <boxGeometry args={[1.5, 1.5, 1.5]} />;
    case 'hexagon':
      return <cylinderGeometry args={[0.95, 0.95, 1.35, 6]} />;
    case 'diamond':
      return <octahedronGeometry args={[1.15, 0]} />;
    case 'triangle':
      return <coneGeometry args={[1.05, 1.7, 4]} />;
    case 'circle':
      return <icosahedronGeometry args={[1, detail]} />;
    default: {
      const _exhaustive: never = shape;
      throw new Error(`Unhandled glyph shape: ${String(_exhaustive)}`);
    }
  }
}

function TypedNodeInstances({
  shape,
  nodes,
  profile,
  onSelect,
  onHover,
}: {
  shape: SceneNode['glyphShape'];
  nodes: SceneNode[];
  profile: SceneQualityProfile;
  onSelect: (nodeId: string) => void;
  onHover: (nodeId: string | null) => void;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) {
      return;
    }
    applyInstancedNodeAttributes(mesh, nodes);
  }, [nodes]);

  return (
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
      <TypedGeometry shape={shape} profile={profile} />
      {/* No `vertexColors` on these materials: per-instance tinting rides on
          setColorAt()'s instanceColor (USE_INSTANCING_COLOR). `vertexColors`
          additionally defines USE_COLOR, whose per-vertex `color` attribute
          this geometry never provides — the unbound attribute reads
          (0, 0, 0) on ANGLE and multiplies every instance color to black. */}
      {profile.material === 'physical' ? (
        <meshPhysicalMaterial
          roughness={0.32}
          metalness={0.22}
          clearcoat={0.7}
          clearcoatRoughness={0.28}
          onBeforeCompile={injectInstanceEmissive}
          customProgramCacheKey={instanceEmissiveCacheKey}
        />
      ) : (
        <meshStandardMaterial
          roughness={0.46}
          metalness={0.14}
          onBeforeCompile={injectInstanceEmissive}
          customProgramCacheKey={instanceEmissiveCacheKey}
        />
      )}
    </instancedMesh>
  );
}

/** The city itself: one instanced mesh per structure silhouette. */
function NodeCity({
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
  const groups = useMemo(() => {
    const byShape = new Map<SceneNode['glyphShape'], SceneNode[]>();
    for (const node of nodes) {
      const bucket = byShape.get(node.glyphShape);
      if (bucket) {
        bucket.push(node);
      } else {
        byShape.set(node.glyphShape, [node]);
      }
    }
    return GLYPH_ORDER.filter((shape) => byShape.has(shape)).map((shape) => ({
      shape,
      members: byShape.get(shape) ?? [],
    }));
  }, [nodes]);

  return (
    <group>
      {groups.map(({ shape, members }) => (
        <TypedNodeInstances
          key={shape}
          shape={shape}
          nodes={members}
          profile={profile}
          onSelect={onSelect}
          onHover={onHover}
        />
      ))}
    </group>
  );
}

/** Light pylons anchoring every structure to its platform. */
function NodePylons({ nodes }: { nodes: SceneNode[] }) {
  const meshRef = useRef<THREE.InstancedMesh>(null);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) {
      return;
    }
    applyPylonAttributes(mesh, nodes);
  }, [nodes]);

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, Math.max(nodes.length, 1)]}
      raycast={() => undefined}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial
        transparent
        opacity={0.55}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

function circlePoints(radius: number, y: number, segments = 64): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  for (let index = 0; index <= segments; index += 1) {
    const angle = (index / segments) * Math.PI * 2;
    points.push(new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius));
  }
  return points;
}

function ZoneRim({
  zone,
  reducedMotion,
}: {
  zone: SceneZone;
  reducedMotion: boolean;
}) {
  const materialRef = useRef<THREE.MeshBasicMaterial>(null);
  const baseOpacity = ALERT_RIM_OPACITY[zone.alertLevel];
  const pulses = !reducedMotion && zone.alertLevel === 'critical';

  useFrame(() => {
    const material = materialRef.current;
    if (!material || !pulses) {
      return;
    }
    material.opacity = baseOpacity * (0.72 + 0.28 * Math.sin(getGraphAnimationTime() * 3.1));
  });

  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.4, 0]}>
      <torusGeometry args={[zone.radius + 1.5, 1, 8, 72]} />
      <meshBasicMaterial
        ref={materialRef}
        color={resolveThreeColor(ALERT_RIM[zone.alertLevel]).color}
        transparent
        opacity={baseOpacity}
        toneMapped={false}
        depthWrite={false}
      />
    </mesh>
  );
}

/** Sector platforms: disc, alert rim, band etchings, nameplate. */
function ZonePlatforms({
  zones,
  profile,
  reducedMotion,
}: {
  zones: SceneZone[];
  profile: SceneQualityProfile;
  reducedMotion: boolean;
}) {
  return (
    <group>
      {zones.map((zone) => {
        const labelTexture = getZoneLabelTexture(
          zone.label,
          zone.alertLevel === 'calm' ? '#c9d4e8' : ALERT_RIM[zone.alertLevel],
        );
        const outward =
          zone.center.x === 0 && zone.center.z === 0
            ? { x: 0, z: 1 }
            : { x: Math.cos(zone.angle), z: Math.sin(zone.angle) };
        return (
          <group key={zone.id} position={[zone.center.x, 0, zone.center.z]}>
            <mesh position={[0, -3.2, 0]} receiveShadow={profile.shadows}>
              <cylinderGeometry args={[zone.radius, zone.radius * 1.05, 6, 48]} />
              <meshStandardMaterial
                color={resolveThreeColor('#0e121b').color}
                roughness={0.86}
                metalness={0.32}
                emissive={resolveThreeColor('#0d1220').color}
                emissiveIntensity={0.85}
              />
            </mesh>
            <ZoneRim zone={zone} reducedMotion={reducedMotion} />
            {[0.3, 0.66, 0.94].map((fraction) => (
              <Line
                key={fraction}
                points={circlePoints(zone.radius * fraction, 0.3)}
                color={resolveThreeColor('#1c2434').color}
                lineWidth={0.8}
                transparent
                opacity={0.85}
                depthWrite={false}
                toneMapped={false}
              />
            ))}
            {labelTexture ? (
              <sprite
                position={[outward.x * (zone.radius + 18), 26, outward.z * (zone.radius + 18)]}
                scale={[110, 20.6, 1]}
                renderOrder={11}
              >
                <spriteMaterial
                  map={labelTexture}
                  transparent
                  opacity={1}
                  depthWrite={false}
                  toneMapped={false}
                />
              </sprite>
            ) : null}
            {zone.alertLevel === 'critical' && profile.glow ? (
              <pointLight
                position={[0, 46, 0]}
                intensity={9_000}
                distance={zone.radius * 2.6}
                decay={2}
                color={resolveThreeColor(ALERT_RIM.critical).color}
              />
            ) : null}
          </group>
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
 * Semantic edges as arcs: intra-zone links hug their platform, inter-zone
 * highways rise over the ring interior. Flow uses the dash-offset uniform of
 * the fat-line material driven from the shared animation clock in useFrame —
 * scalar uniform writes only, no allocation, no rebuild.
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
    const byId = new Map(nodes.map((node) => [node.id, node]));
    return edges
      .map((edge) => {
        const source = byId.get(edge.sourceId);
        const target = byId.get(edge.targetId);
        if (!source || !target) {
          return null;
        }
        const kind: EdgeArcKind = edgeArcKind(source.clusterId, target.clusterId);
        const resolved = resolveThreeColor(edge.color, '#94a3b8');
        // Fog of war: a link touching an undetected asset stays a faint
        // filament — the topology is visible, its meaning is not.
        const fogged = !source.disclosed || !target.disclosed;
        // Flow gating: 'full' animates every flow-capable edge; 'coarse'
        // (MEDIUM tier) only edges on the current selection/highlight;
        // 'static' (reduced motion / LOW tier) animates nothing.
        const flowAnimated =
          !fogged &&
          edge.flowSpeed > 0 &&
          flowProfile !== 'static' &&
          (flowProfile === 'full' || edge.highlighted);
        return {
          edge,
          kind,
          color: fogged ? resolveThreeColor('#3d4656').color : resolved.color,
          opacity: (fogged ? 0.3 : 1) * edge.opacity * resolved.opacity,
          flowAnimated,
          points: edgeArcPoints(source.position, target.position, kind).map(
            (point) => new THREE.Vector3(point.x, point.y, point.z),
          ),
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
      {segments.map(({ edge, kind, color, opacity, flowAnimated, points }) => {
        // Containment keeps a short static dash; alive flow uses a long,
        // low-contrast travelling dash. Static profile: containment stays
        // dashed (it is semantic), flow edges render solid.
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
            lineWidth={Math.max(
              0.75,
              edge.width * profile.edgeWidthScale * (kind === 'inter' ? 1.15 : 0.9),
            )}
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
              // Sprite-halo billboard behind the node reusing the existing
              // radial-falloff shader; uColor carries the risk color,
              // uOpacity scales with severity.
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
                    ? resolveThreeColor('#f2ca6b').color
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

interface SigilRefs {
  scanRings: THREE.Mesh[];
  beamMaterials: THREE.MeshBasicMaterial[];
  haloMaterials: THREE.ShaderMaterial[];
}

/**
 * Threat sigils — the attacker made visible. Only disclosed, non-normal
 * assets earn one: suspicious breathes amber, under-investigation carries a
 * scanning ring, compromised burns with a vertical beam, contained sits in a
 * cold cage. All animation funnels through one useFrame walking ref arrays.
 */
function ThreatSigils({
  nodes,
  profile,
  reducedMotion,
}: {
  nodes: SceneNode[];
  profile: SceneQualityProfile;
  reducedMotion: boolean;
}) {
  const marked = useMemo(
    () => nodes.filter((node) => node.disclosed && node.status !== 'normal' && !node.dimmed),
    [nodes],
  );
  const compromised = useMemo(
    () => marked.filter((node) => node.status === 'compromised'),
    [marked],
  );

  const refs = useRef<SigilRefs>({ scanRings: [], beamMaterials: [], haloMaterials: [] });
  refs.current.scanRings = [];
  refs.current.beamMaterials = [];
  refs.current.haloMaterials = [];

  useFrame(() => {
    if (reducedMotion) {
      return;
    }
    const time = getGraphAnimationTime();
    for (const ring of refs.current.scanRings) {
      ring.rotation.z = time * 0.9;
    }
    const beamPulse = 0.4 + 0.2 * Math.sin(time * 4.2);
    for (const material of refs.current.beamMaterials) {
      material.opacity = beamPulse;
    }
    const haloPulse = 0.55 + 0.3 * Math.sin(time * 2.6);
    for (const material of refs.current.haloMaterials) {
      const uniform = material.uniforms['uOpacity'];
      if (uniform) {
        uniform.value = (material.userData['baseOpacity'] as number) * haloPulse;
      }
    }
  });

  return (
    <group>
      {marked.map((node) => {
        const radius = nodeRadius(node);
        const tint = STATUS_TINTS[node.status] ?? '#f1c257';
        const color = resolveThreeColor(tint).color;
        const position: [number, number, number] = [
          node.position.x,
          node.position.y,
          node.position.z,
        ];

        return (
          <group key={`sigil-${node.id}`}>
            {/* Status gem above the structure — small, always legible, the
                shared status color language. */}
            <mesh position={[position[0], position[1] + radius + 4.5, position[2]]}>
              <octahedronGeometry args={[2.1, 0]} />
              <meshBasicMaterial color={color} toneMapped={false} />
            </mesh>

            {profile.glow && (node.status === 'suspicious' || node.status === 'compromised') ? (
              <Billboard position={position}>
                <mesh scale={radius * (node.status === 'compromised' ? 4.6 : 3.4)} renderOrder={3}>
                  <planeGeometry args={[1, 1]} />
                  <shaderMaterial
                    ref={(material: THREE.ShaderMaterial | null) => {
                      if (material) {
                        material.userData['baseOpacity'] =
                          node.status === 'compromised' ? 0.62 : 0.38;
                        refs.current.haloMaterials.push(material);
                      }
                    }}
                    vertexShader={RISK_HALO_VERTEX}
                    fragmentShader={RISK_HALO_FRAGMENT}
                    uniforms={{
                      uColor: { value: color },
                      uOpacity: { value: node.status === 'compromised' ? 0.62 : 0.38 },
                    }}
                    transparent
                    depthWrite={false}
                    blending={THREE.AdditiveBlending}
                  />
                </mesh>
              </Billboard>
            ) : null}

            {node.status === 'under_investigation' ? (
              <mesh
                ref={(mesh: THREE.Mesh | null) => {
                  if (mesh) {
                    refs.current.scanRings.push(mesh);
                  }
                }}
                position={position}
                rotation={[Math.PI / 2, 0, 0]}
              >
                <torusGeometry args={[radius * 1.8, 0.55, 6, 48, Math.PI * 1.45]} />
                <meshBasicMaterial
                  color={color}
                  transparent
                  opacity={0.85}
                  toneMapped={false}
                  depthWrite={false}
                />
              </mesh>
            ) : null}

            {node.status === 'contained' ? (
              <mesh position={position}>
                <octahedronGeometry args={[radius * 1.85, 0]} />
                <meshBasicMaterial
                  color={color}
                  wireframe
                  transparent
                  opacity={0.5}
                  toneMapped={false}
                  depthWrite={false}
                />
              </mesh>
            ) : null}

            {node.status === 'compromised' ? (
              <mesh position={[position[0], position[1] + 46, position[2]]}>
                <cylinderGeometry args={[1.3, 2.6, 96, 8, 1, true]} />
                <meshBasicMaterial
                  ref={(material: THREE.MeshBasicMaterial | null) => {
                    if (material) {
                      refs.current.beamMaterials.push(material);
                    }
                  }}
                  color={color}
                  transparent
                  opacity={0.5}
                  side={THREE.DoubleSide}
                  blending={THREE.AdditiveBlending}
                  depthWrite={false}
                  toneMapped={false}
                />
              </mesh>
            ) : null}
          </group>
        );
      })}

      {/* Ember light for the fiercest breaches — capped so a mass compromise
          cannot melt the GPU with dynamic lights. */}
      {profile.glow
        ? compromised.slice(0, 4).map((node) => (
            <pointLight
              key={`ember-${node.id}`}
              position={[node.position.x, node.position.y + 26, node.position.z]}
              intensity={7_000}
              distance={210}
              decay={2}
              color={resolveThreeColor(STATUS_TINTS['compromised'] ?? '#ff7078').color}
            />
          ))
        : null}
    </group>
  );
}

interface RevealPulse {
  key: string;
  x: number;
  z: number;
  color: string;
  start: number;
}

const REVEAL_SECONDS = 1.7;

/**
 * Reveal shockwaves: when fog of war lifts on a hostile asset — or an asset
 * escalates to compromised / drops to contained — a ring detonates outward
 * across its platform. Pure presentation of a state *transition*; the steady
 * state is carried by the sigils and materials.
 */
function RevealPulses({ nodes, reducedMotion }: { nodes: SceneNode[]; reducedMotion: boolean }) {
  const previousRef = useRef<Map<string, { disclosed: boolean; status: string }> | null>(null);
  const [pulses, setPulses] = useState<RevealPulse[]>([]);
  const meshRefs = useRef(new Map<string, THREE.Mesh>());

  useEffect(() => {
    const previous = previousRef.current;
    const next = new Map<string, { disclosed: boolean; status: string }>();
    for (const node of nodes) {
      next.set(node.id, { disclosed: node.disclosed, status: node.status });
    }
    // First projection is baseline — arriving mid-run must not detonate a
    // firework for every already-known fact.
    if (previous !== null && !reducedMotion) {
      const spawned: RevealPulse[] = [];
      const now = getGraphAnimationTime();
      for (const node of nodes) {
        const before = previous.get(node.id);
        if (!before) {
          continue;
        }
        const revealed = !before.disclosed && node.disclosed && node.status !== 'normal';
        const ignited = before.status !== 'compromised' && node.status === 'compromised';
        const severed = before.status !== 'contained' && node.status === 'contained';
        if (revealed || (node.disclosed && (ignited || severed))) {
          spawned.push({
            key: `${node.id}:${String(now)}`,
            x: node.position.x,
            z: node.position.z,
            color: STATUS_TINTS[node.status] ?? '#f1c257',
            start: now,
          });
        }
      }
      if (spawned.length > 0) {
        setPulses((current) => [...current, ...spawned].slice(-12));
        const timer = setTimeout(() => {
          setPulses((current) => current.filter((pulse) => !spawned.includes(pulse)));
        }, REVEAL_SECONDS * 1000 + 400);
        previousRef.current = next;
        return () => {
          clearTimeout(timer);
        };
      }
    }
    previousRef.current = next;
    return undefined;
  }, [nodes, reducedMotion]);

  useFrame(() => {
    if (pulses.length === 0) {
      return;
    }
    const time = getGraphAnimationTime();
    for (const pulse of pulses) {
      const mesh = meshRefs.current.get(pulse.key);
      if (!mesh) {
        continue;
      }
      const progress = Math.min(1, (time - pulse.start) / REVEAL_SECONDS);
      const eased = 1 - Math.pow(1 - progress, 2);
      mesh.scale.setScalar(4 + eased * 120);
      const material = mesh.material as THREE.MeshBasicMaterial;
      material.opacity = (1 - progress) * 0.85;
      mesh.visible = progress < 1;
    }
  });

  if (reducedMotion) {
    return null;
  }

  return (
    <group>
      {pulses.map((pulse) => (
        <mesh
          key={pulse.key}
          ref={(mesh: THREE.Mesh | null) => {
            if (mesh) {
              meshRefs.current.set(pulse.key, mesh);
            } else {
              meshRefs.current.delete(pulse.key);
            }
          }}
          position={[pulse.x, 0.8, pulse.z]}
          rotation={[-Math.PI / 2, 0, 0]}
          renderOrder={5}
        >
          <ringGeometry args={[0.88, 1, 48]} />
          <meshBasicMaterial
            color={resolveThreeColor(pulse.color).color}
            transparent
            opacity={0.85}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

/**
 * Labels stay off at rest — the floating node card appears on selection or
 * hover only, matching the 2D canvas hover/select behavior. The accessible
 * entity list below the canvas covers everything else.
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
          {node.disclosed
            ? `Risk ${String(Math.round(node.riskScore * 100))}${
                node.status !== 'normal' ? ` · ${node.status.replaceAll('_', ' ')}` : ''
              }`
            : 'Not yet detected'}
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

/** Deterministic LCG so the starfield never twinkles differently per mount. */
function starfieldPositions(count: number): Float32Array {
  const positions = new Float32Array(count * 3);
  let seed = 1337;
  const random = () => {
    seed = (seed * 1_664_525 + 1_013_904_223) >>> 0;
    return seed / 0xffffffff;
  };
  for (let index = 0; index < count; index += 1) {
    const radius = 1_500 + random() * 1_100;
    const theta = random() * Math.PI * 2;
    const y = -500 + random() * 1_600;
    positions[index * 3] = Math.cos(theta) * radius;
    positions[index * 3 + 1] = y;
    positions[index * 3 + 2] = Math.sin(theta) * radius;
  }
  return positions;
}

/** The void: polar deck grid beneath the ring, sparse static particle field. */
function SceneAtmosphere({ zones }: { zones: SceneZone[] }) {
  const deckRadius = useMemo(() => {
    if (zones.length === 0) {
      return 640;
    }
    return (
      Math.max(
        ...zones.map((zone) => Math.hypot(zone.center.x, zone.center.z) + zone.radius),
      ) + 150
    );
  }, [zones]);

  const stars = useMemo(() => starfieldPositions(420), []);

  return (
    <group>
      <polarGridHelper
        args={[
          deckRadius,
          16,
          8,
          96,
          resolveThreeColor('#151c2b').color,
          resolveThreeColor('#0b101b').color,
        ]}
        position={[0, -42, 0]}
      />
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[stars, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={2.4}
          sizeAttenuation
          color={resolveThreeColor('#40527c').color}
          transparent
          opacity={0.5}
          depthWrite={false}
        />
      </points>
    </group>
  );
}

export interface CinematicSceneCanvasProps {
  nodes: SceneNode[];
  edges: SceneEdge[];
  zones: SceneZone[];
  camera: CameraBookmark3D;
  qualityTier: RenderQualityTierValue;
  dprCap: number;
  reducedMotion: boolean;
  /** Flow gate resolved by the view from the capability report. */
  flowProfile: EdgeFlowProfile;
  onReady: () => void;
  onSelectNode: (nodeId: string) => void;
  onBackgroundClick: () => void;
}

export function CinematicSceneCanvas({
  nodes,
  edges,
  zones,
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
      aria-label="3D operations theater: sector platforms of the bastion ring"
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
          gl.toneMappingExposure = qualityTier === RenderQualityTier.HIGH ? 1.26 : 1.12;
          gl.shadowMap.enabled = profile.shadows;
          gl.shadowMap.type = THREE.PCFSoftShadowMap;
          gl.setClearColor(new THREE.Color(VOID_BG), 1);
          onReady();
        }}
      >
        <color attach="background" args={[resolveThreeColor(VOID_BG).color]} />
        <fog
          attach="fog"
          args={[resolveThreeColor(FOG_COLOR).color, profile.fogNear, profile.fogFar]}
        />
        <ambientLight intensity={0.32} />
        <hemisphereLight
          args={[
            resolveThreeColor('#3d4c66').color,
            resolveThreeColor('#05070c').color,
            0.9,
          ]}
        />
        <directionalLight
          position={[420, 700, 260]}
          intensity={1.95}
          color={resolveThreeColor('#dfe8f5').color}
          castShadow={profile.shadows}
        />
        <directionalLight
          position={[-380, 220, -420]}
          intensity={0.5}
          color={resolveThreeColor('#5a6f96').color}
        />
        <CameraController bookmark={camera} reducedMotion={reducedMotion} />
        <SceneAtmosphere zones={zones} />
        <ZonePlatforms zones={zones} profile={profile} reducedMotion={reducedMotion} />
        <SceneEdges edges={edges} nodes={nodes} profile={profile} flowProfile={flowProfile} />
        <NodePylons nodes={nodes} />
        <RiskAndSelectionAccents nodes={nodes} profile={profile} />
        <NodeCity nodes={nodes} profile={profile} onSelect={onSelectNode} onHover={setHoveredNodeId} />
        <ThreatSigils nodes={nodes} profile={profile} reducedMotion={reducedMotion} />
        <RevealPulses nodes={nodes} reducedMotion={reducedMotion} />
        <SceneLabels nodes={nodes} hoveredNodeId={hoveredNodeId} />
      </Canvas>
      <div
        className="cinematic-canvas-vignette pointer-events-none absolute inset-0"
        aria-hidden="true"
      />
    </div>
  );
}
