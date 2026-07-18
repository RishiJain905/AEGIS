import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

export interface LayoutPosition {
  x: number;
  y: number;
}

const CLUSTER_RADIUS = 180;
const NODE_RADIUS = 64;
const TARGET_LAYOUT_ASPECT = 1;
const MAX_HORIZONTAL_STRETCH = 2.5;

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
        x: center.x + Math.cos(angle) * (NODE_RADIUS + clusterNodes.length * 5) + jitter,
        y: center.y + Math.sin(angle) * (NODE_RADIUS + clusterNodes.length * 5) + jitter,
      };
    });
  }

  return positions;
}

export function balanceLayoutAspect(
  positions: Record<string, LayoutPosition>,
  targetAspect = TARGET_LAYOUT_ASPECT,
): Record<string, LayoutPosition> {
  const entries = Object.entries(positions);
  if (entries.length < 2) {
    return { ...positions };
  }

  const xs = entries.map(([, position]) => position.x);
  const ys = entries.map(([, position]) => position.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX;
  const ySpan = maxY - minY;

  if (xSpan < 0.001 || ySpan < 0.001 || xSpan / ySpan >= targetAspect) {
    return { ...positions };
  }

  const centerX = (minX + maxX) / 2;
  const horizontalStretch = Math.min(MAX_HORIZONTAL_STRETCH, (ySpan * targetAspect) / xSpan);

  return Object.fromEntries(
    entries.map(([nodeId, position]) => [
      nodeId,
      {
        x: centerX + (position.x - centerX) * horizontalStretch,
        y: position.y,
      },
    ]),
  );
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
