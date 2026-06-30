import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

export interface LayoutPosition {
  x: number;
  y: number;
}

const CLUSTER_RADIUS = 120;
const NODE_RADIUS = 40;

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function computeInitialLayout(
  nodes: GraphNodeV1[],
  _clusters: GraphClusterV1[],
  existingPositions: Record<string, LayoutPosition> = {},
): Record<string, LayoutPosition> {
  const positions: Record<string, LayoutPosition> = { ...existingPositions };
  const sortedNodes = [...nodes].sort((a, b) => a.id.localeCompare(b.id));

  const clusterIds = [...new Set(sortedNodes.map((n) => n.clusterId ?? 'unclustered'))].sort();
  const clusterCenters: Record<string, { x: number; y: number }> = {};

  clusterIds.forEach((clusterId, clusterIndex) => {
    const angle = (2 * Math.PI * clusterIndex) / Math.max(clusterIds.length, 1);
    clusterCenters[clusterId] = {
      x: Math.cos(angle) * CLUSTER_RADIUS * Math.max(clusterIds.length, 1) * 0.5,
      y: Math.sin(angle) * CLUSTER_RADIUS * Math.max(clusterIds.length, 1) * 0.5,
    };
  });

  const nodesByCluster = new Map<string, GraphNodeV1[]>();
  for (const node of sortedNodes) {
    const key = node.clusterId ?? 'unclustered';
    const group = nodesByCluster.get(key) ?? [];
    group.push(node);
    nodesByCluster.set(key, group);
  }

  for (const [clusterId, clusterNodes] of nodesByCluster) {
    const center = clusterCenters[clusterId] ?? { x: 0, y: 0 };
    clusterNodes.forEach((node, index) => {
      if (positions[node.id]) {
        return;
      }
      const angle = (2 * Math.PI * index) / Math.max(clusterNodes.length, 1);
      const jitter = (hashString(node.id) % 20) - 10;
      positions[node.id] = {
        x: center.x + Math.cos(angle) * (NODE_RADIUS + clusterNodes.length * 3) + jitter,
        y: center.y + Math.sin(angle) * (NODE_RADIUS + clusterNodes.length * 3) + jitter,
      };
    });
  }

  return positions;
}

export function filterNodesBySearch(
  nodeIds: string[],
  nodeLabels: Map<string, string>,
  query: string,
): string[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return nodeIds;
  }
  return nodeIds.filter((id) => {
    const label = nodeLabels.get(id) ?? '';
    return id.toLowerCase().includes(normalized) || label.toLowerCase().includes(normalized);
  });
}
