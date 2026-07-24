import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

/**
 * Bastion-ring layout: the org's zones become sector platforms arranged on a
 * ring floating in the void. Within a platform, assets stratify into
 * concentric bands by asset type — crown jewels (databases, models) at the
 * core, services and controls in the mid band, endpoints and identities on
 * the outer band — and each asset hovers above the platform at a height set
 * by its criticality, so importance reads as skyline and the dark ring
 * interior becomes the stage where cross-zone traffic arcs.
 *
 * Everything here is pure, deterministic presentation geometry: the same
 * nodes and clusters always produce the same placement, independent of graph
 * mutation order, so live deltas never make the city jitter.
 */

export const ZONE_UNASSIGNED_ID = 'zone:unassigned';

/** Minimum ring radius keeps the theater readable even with two tiny zones. */
const MIN_RING_RADIUS = 300;
/** Clearance between adjacent platform rims along the ring. */
const RING_GAP = 64;
/** Clearance between a central (unassigned) platform and the ring. */
const CENTER_GAP = 90;

const MIN_PLATFORM_RADIUS = 46;
const MAX_PLATFORM_RADIUS = 124;

const HOVER_BASE = 16;
const HOVER_CRITICALITY_RANGE = 52;

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

export interface ZonePlacement {
  id: string;
  label: string;
  center: { x: number; y: number; z: number };
  radius: number;
  /** Ring angle in radians; 0 for a central platform. */
  angle: number;
  nodeIds: string[];
}

export interface ZoneLayoutResult {
  positions: Record<string, { x: number; y: number; z: number }>;
  zones: ZonePlacement[];
}

type LayoutNode = Pick<
  GraphNodeV1,
  'id' | 'clusterId' | 'assetType' | 'criticality' | 'entityType'
>;

/** Concentric band per asset type: 0 = core, 1 = mid, 2 = outer. */
export function assetTypeBand(assetType: string | null | undefined): 0 | 1 | 2 {
  switch (assetType) {
    case 'database':
    case 'ai_model':
      return 0;
    case 'service':
    case 'control':
      return 1;
    default:
      return 2;
  }
}

const BAND_FRACTIONS: ReadonlyArray<readonly [number, number]> = [
  [0.0, 0.3],
  [0.4, 0.66],
  [0.72, 0.94],
];

/** FNV-1a 32-bit — a stable, dependency-free hash for deterministic jitter. */
function hash32(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function unitHash(input: string): number {
  return hash32(input) / 0xffffffff;
}

export function platformRadius(memberCount: number): number {
  return Math.min(
    MAX_PLATFORM_RADIUS,
    Math.max(MIN_PLATFORM_RADIUS, 40 + 15 * Math.sqrt(Math.max(memberCount, 1))),
  );
}

export function hoverHeight(criticality: number): number {
  return HOVER_BASE + Math.min(1, Math.max(0, criticality)) * HOVER_CRITICALITY_RANGE;
}

export function deriveZoneLabel(zoneId: string, clusters: readonly GraphClusterV1[]): string {
  const cluster = clusters.find((entry) => entry.id === zoneId);
  if (cluster) {
    return cluster.label;
  }
  if (zoneId === ZONE_UNASSIGNED_ID) {
    return 'Unassigned';
  }
  const tail = zoneId.split(':').pop() ?? zoneId;
  return tail.replace(/[-_]+/g, ' ').trim() || zoneId;
}

interface ZoneBucket {
  id: string;
  nodes: LayoutNode[];
}

function bucketNodesByZone(nodes: readonly LayoutNode[]): ZoneBucket[] {
  const buckets = new Map<string, LayoutNode[]>();
  for (const node of nodes) {
    const zoneId = node.clusterId ?? ZONE_UNASSIGNED_ID;
    const bucket = buckets.get(zoneId);
    if (bucket) {
      bucket.push(node);
    } else {
      buckets.set(zoneId, [node]);
    }
  }
  return [...buckets.entries()]
    .map(([id, members]) => ({ id, nodes: [...members].sort((a, b) => a.id.localeCompare(b.id)) }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

function placeWithinPlatform(
  zoneId: string,
  radius: number,
  members: readonly LayoutNode[],
): Map<string, { x: number; z: number }> {
  const local = new Map<string, { x: number; z: number }>();
  for (let band = 0 as 0 | 1 | 2; band <= 2; band = (band + 1) as 0 | 1 | 2) {
    const bandMembers = members.filter((node) => assetTypeBand(node.assetType) === band);
    const count = bandMembers.length;
    if (count === 0) {
      continue;
    }
    const [innerFraction, outerFraction] = BAND_FRACTIONS[band] ?? [0.5, 0.9];
    const inner = innerFraction * radius;
    const outer = outerFraction * radius;
    const startAngle = unitHash(`${zoneId}:band:${String(band)}`) * Math.PI * 2;

    if (band === 0 && count === 1) {
      const only = bandMembers[0];
      if (only) {
        local.set(only.id, { x: 0, z: 0 });
      }
      continue;
    }

    bandMembers.forEach((node, index) => {
      let r: number;
      let angle: number;
      if (count <= 12) {
        // Even ring with a deterministic radial breathing so the band reads
        // organic instead of machine-stamped.
        const mid = (inner + outer) / 2;
        const jitter = (unitHash(node.id) * 2 - 1) * (outer - inner) * 0.28;
        r = mid + jitter;
        angle = startAngle + (index / count) * Math.PI * 2;
      } else {
        // Sunflower fill for dense bands: uniform coverage of the annulus.
        const t = (index + 0.5) / count;
        r = inner + (outer - inner) * Math.sqrt(t);
        angle = startAngle + index * GOLDEN_ANGLE;
      }
      local.set(node.id, { x: Math.cos(angle) * r, z: Math.sin(angle) * r });
    });
  }
  return local;
}

export function computeZoneLayout(
  nodes: readonly LayoutNode[],
  clusters: readonly GraphClusterV1[] = [],
): ZoneLayoutResult {
  const buckets = bucketNodesByZone(nodes);
  if (buckets.length === 0) {
    return { positions: {}, zones: [] };
  }

  const centerBucket = buckets.find((bucket) => bucket.id === ZONE_UNASSIGNED_ID) ?? null;
  const ringBuckets = buckets.filter((bucket) => bucket.id !== ZONE_UNASSIGNED_ID);

  const radiusById = new Map(
    buckets.map((bucket) => [bucket.id, platformRadius(bucket.nodes.length)]),
  );

  // Ring radius: adjacent platforms must clear each other along the ring, and
  // the whole ring must clear any central platform.
  let ringRadius = 0;
  const ringCount = ringBuckets.length;
  if (ringCount === 1) {
    ringRadius = centerBucket
      ? (radiusById.get(centerBucket.id) ?? 0) + (radiusById.get(ringBuckets[0]?.id ?? '') ?? 0) + CENTER_GAP
      : 0;
  } else if (ringCount > 1) {
    const halfChord = Math.sin(Math.PI / ringCount);
    for (let index = 0; index < ringCount; index += 1) {
      const a = radiusById.get(ringBuckets[index]?.id ?? '') ?? MIN_PLATFORM_RADIUS;
      const b =
        radiusById.get(ringBuckets[(index + 1) % ringCount]?.id ?? '') ?? MIN_PLATFORM_RADIUS;
      ringRadius = Math.max(ringRadius, (a + b + RING_GAP) / (2 * halfChord));
    }
    ringRadius = Math.max(ringRadius, MIN_RING_RADIUS);
    if (centerBucket) {
      const centerRadius = radiusById.get(centerBucket.id) ?? MIN_PLATFORM_RADIUS;
      const maxRing = Math.max(
        ...ringBuckets.map((bucket) => radiusById.get(bucket.id) ?? MIN_PLATFORM_RADIUS),
      );
      ringRadius = Math.max(ringRadius, centerRadius + maxRing + CENTER_GAP);
    }
  }

  const positions: Record<string, { x: number; y: number; z: number }> = {};
  const zones: ZonePlacement[] = [];

  const placeZone = (bucket: ZoneBucket, center: { x: number; z: number }, angle: number) => {
    const radius = radiusById.get(bucket.id) ?? MIN_PLATFORM_RADIUS;
    const local = placeWithinPlatform(bucket.id, radius, bucket.nodes);
    for (const node of bucket.nodes) {
      const offset = local.get(node.id) ?? { x: 0, z: 0 };
      positions[node.id] = {
        x: center.x + offset.x,
        y: hoverHeight(node.criticality),
        z: center.z + offset.z,
      };
    }
    zones.push({
      id: bucket.id,
      label: deriveZoneLabel(bucket.id, clusters),
      center: { x: center.x, y: 0, z: center.z },
      radius,
      angle,
      nodeIds: bucket.nodes.map((node) => node.id),
    });
  };

  ringBuckets.forEach((bucket, index) => {
    const angle = -Math.PI / 2 + (index / Math.max(ringCount, 1)) * Math.PI * 2;
    placeZone(
      bucket,
      { x: Math.cos(angle) * ringRadius, z: Math.sin(angle) * ringRadius },
      angle,
    );
  });
  if (centerBucket) {
    placeZone(centerBucket, { x: 0, z: 0 }, 0);
  }

  return { positions, zones };
}

export type ZoneAlertLevel = 'calm' | 'guarded' | 'elevated' | 'critical';

/**
 * Presentation rollup of a zone's disclosed statuses. Active threat outranks a
 * severed one: compromised > suspicious/under investigation > contained > calm.
 * Undisclosed nodes must be excluded by the caller — fog of war means their
 * true state cannot tint the platform.
 */
export function zoneAlertLevel(statuses: readonly string[]): ZoneAlertLevel {
  let level: ZoneAlertLevel = 'calm';
  for (const status of statuses) {
    if (status === 'compromised') {
      return 'critical';
    }
    if (status === 'suspicious' || status === 'under_investigation') {
      level = 'elevated';
    } else if (status === 'contained' && level === 'calm') {
      level = 'guarded';
    }
  }
  return level;
}
