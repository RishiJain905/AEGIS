import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

export interface LayoutPosition {
  x: number;
  y: number;
}

/** Deterministic placement of one zone (cluster) on the sector board. */
export interface ZonePlacement {
  id: string;
  label: string;
  center: LayoutPosition;
  /** Radius of the disc reserved for member nodes (hull padding excluded). */
  radius: number;
  memberIds: string[];
}

export interface ZoneLayoutResult {
  positions: Record<string, LayoutPosition>;
  zones: ZonePlacement[];
}

export const UNZONED_CLUSTER_ID = 'unclustered';

// Distances are in graph units. Sigma fits the whole board to the viewport, so
// only the ratios matter: ring spacing controls intra-zone density, cell size
// controls how far apart zones read. MIN_CELL keeps single-node zones from
// crowding (and keeps the legacy readability floor of >420 units between
// isolated cluster anchors).
const RING_SPACING = 76;
const ZONE_HULL_PADDING = 52;
const ZONE_CELL_GUTTER = 150;
const MIN_CELL_SIZE = 460;
/** Extra slack beyond the node disc that the force worker may use. */
const ZONE_CONSTRAINT_SLACK = ZONE_HULL_PADDING * 0.5;

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

/**
 * Human-readable zone label derived from the cluster id when the snapshot does
 * not carry cluster metadata (live projections send `clusters: []`), e.g.
 * `business-unit:ai-ops` -> `AI OPS`.
 */
export function zoneLabelFromClusterId(clusterId: string): string {
  if (clusterId === UNZONED_CLUSTER_ID) {
    return 'UNZONED';
  }
  const separator = clusterId.indexOf(':');
  const slug = separator >= 0 ? clusterId.slice(separator + 1) : clusterId;
  return slug.split(/[-_]+/).filter(Boolean).join(' ').toUpperCase();
}

/** Ring index (0 = center) and slot for the i-th member of a zone. Ring k
 * holds 6k nodes, so capacity grows with circumference and radius stays
 * proportional to sqrt(memberCount). */
function ringSlot(index: number): { ring: number; slot: number; ringCapacity: number } {
  if (index === 0) {
    return { ring: 0, slot: 0, ringCapacity: 1 };
  }
  let ring = 1;
  let firstIndexOfRing = 1;
  while (index >= firstIndexOfRing + 6 * ring) {
    firstIndexOfRing += 6 * ring;
    ring += 1;
  }
  return { ring, slot: index - firstIndexOfRing, ringCapacity: 6 * ring };
}

function zoneNodeRadius(memberCount: number): number {
  if (memberCount <= 1) {
    return RING_SPACING * 0.6;
  }
  const { ring } = ringSlot(memberCount - 1);
  return Math.max(RING_SPACING * 0.6, ring * RING_SPACING);
}

/**
 * The zone sector board: every zone gets its own region on a deterministic
 * grid, and members fill the zone disc on concentric rings ordered by
 * criticality (most critical asset at the zone center). Nothing depends on
 * force simulation, so 38 nodes can never collapse into a central hairball —
 * the org's structure is the layout.
 *
 * Existing positions always win (positions are preserved during a run); zone
 * geometry is computed from the full membership regardless, so hulls and
 * constraints stay stable as nodes appear.
 */
export function computeZoneLayout(
  nodes: GraphNodeV1[],
  clusters: GraphClusterV1[],
  existingPositions: Record<string, LayoutPosition> = {},
): ZoneLayoutResult {
  const positions: Record<string, LayoutPosition> = { ...existingPositions };
  const clusterLabels = new Map(clusters.map((cluster) => [cluster.id, cluster.label]));

  const nodesByZone = new Map<string, GraphNodeV1[]>();
  for (const node of [...nodes].sort((a, b) => a.id.localeCompare(b.id))) {
    const zoneId = node.clusterId ?? UNZONED_CLUSTER_ID;
    const group = nodesByZone.get(zoneId) ?? [];
    group.push(node);
    nodesByZone.set(zoneId, group);
  }

  const zoneIds = [...nodesByZone.keys()].sort();
  const radii = zoneIds.map((zoneId) => zoneNodeRadius(nodesByZone.get(zoneId)?.length ?? 0));
  const maxRadius = radii.length > 0 ? Math.max(...radii) : RING_SPACING;
  const cellSize = Math.max(MIN_CELL_SIZE, 2 * (maxRadius + ZONE_HULL_PADDING) + ZONE_CELL_GUTTER);

  // Wide command-board aspect: for 8 zones this resolves to a 4x2 grid.
  const columns = Math.max(1, Math.ceil(Math.sqrt(zoneIds.length * 2)));
  const rows = Math.max(1, Math.ceil(zoneIds.length / columns));

  const zones: ZonePlacement[] = zoneIds.map((zoneId, zoneIndex) => {
    const members = nodesByZone.get(zoneId) ?? [];
    const column = zoneIndex % columns;
    const row = Math.floor(zoneIndex / columns);
    const center = {
      x: (column - (columns - 1) / 2) * cellSize,
      y: (row - (rows - 1) / 2) * cellSize * 0.95,
    };

    // Most critical assets at the zone center where the eye lands first;
    // ties broken by id for determinism.
    const ordered = [...members].sort(
      (a, b) => b.criticality - a.criticality || a.id.localeCompare(b.id),
    );
    const phase = ((hashString(zoneId) % 360) * Math.PI) / 180;

    ordered.forEach((node, index) => {
      if (positions[node.id]) {
        return;
      }
      const { ring, slot, ringCapacity } = ringSlot(index);
      if (ring === 0) {
        positions[node.id] = { x: center.x, y: center.y };
        return;
      }
      const remaining = ordered.length - (index - slot);
      const occupancy = Math.min(ringCapacity, remaining);
      const angle = phase + ring * 0.35 + (2 * Math.PI * slot) / Math.max(occupancy, 1);
      positions[node.id] = {
        x: center.x + Math.cos(angle) * ring * RING_SPACING,
        y: center.y + Math.sin(angle) * ring * RING_SPACING,
      };
    });

    return {
      id: zoneId,
      label: clusterLabels.get(zoneId) ?? zoneLabelFromClusterId(zoneId),
      center,
      radius: zoneNodeRadius(members.length),
      memberIds: ordered.map((node) => node.id),
    };
  });

  return { positions, zones };
}

export interface ZoneConstraint {
  x: number;
  y: number;
  radius: number;
}

/** Per-zone containment discs for the layout worker: ForceAtlas2 may refine
 * placement inside a zone but can never pull a node out of its sector. */
export function zoneConstraintsFromLayout(zones: ZonePlacement[]): Record<string, ZoneConstraint> {
  const constraints: Record<string, ZoneConstraint> = {};
  for (const zone of zones) {
    constraints[zone.id] = {
      x: zone.center.x,
      y: zone.center.y,
      radius: zone.radius + ZONE_CONSTRAINT_SLACK,
    };
  }
  return constraints;
}
