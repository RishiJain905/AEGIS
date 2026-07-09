import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

import { computeInitialLayout } from '@/features/operational-graph/layout/initial-layout';

const CLUSTER_Z_SPACING = 48;

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

/**
 * Deterministic Z from cluster identity so 3D positions stay stable across
 * mode switches and replay scrubbing without writing into domain state.
 */
export function clusterZ(clusterId: string | null | undefined): number {
  const key = clusterId ?? 'unclustered';
  const bucket = hashString(key) % 7;
  return (bucket - 3) * CLUSTER_Z_SPACING;
}

export function toScenePosition(
  xy: { x: number; y: number },
  clusterId: string | null | undefined,
): { x: number; y: number; z: number } {
  return {
    x: xy.x,
    y: xy.y,
    z: clusterZ(clusterId),
  };
}

export function resolveStablePositions(
  nodes: GraphNodeV1[],
  clusters: GraphClusterV1[],
  existingPositions: Record<string, { x: number; y: number }> = {},
  workerPositions: Record<string, { x: number; y: number }> = {},
): Record<string, { x: number; y: number; z: number }> {
  const layout2d = computeInitialLayout(nodes, clusters, {
    ...existingPositions,
    ...workerPositions,
  });
  const result: Record<string, { x: number; y: number; z: number }> = {};
  for (const node of nodes) {
    const xy = layout2d[node.id] ?? { x: 0, y: 0 };
    result[node.id] = toScenePosition(xy, node.clusterId);
  }
  return result;
}
