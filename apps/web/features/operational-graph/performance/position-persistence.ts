import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';

import type { LayoutPosition } from '../layout/initial-layout';

export function mergePositionRecords(
  base: Record<string, LayoutPosition>,
  incoming: Record<string, LayoutPosition>,
): Record<string, LayoutPosition> {
  return { ...base, ...incoming };
}

export function applyPinnedPositions(
  positions: Record<string, LayoutPosition>,
  pinnedNodeIds: string[],
  pinnedPositions: Record<string, LayoutPosition>,
): Record<string, LayoutPosition> {
  const next = { ...positions };
  for (const nodeId of pinnedNodeIds) {
    const pinned = pinnedPositions[nodeId];
    if (pinned) {
      next[nodeId] = pinned;
    }
  }
  return next;
}

export function positionsFromNodes(
  nodes: GraphNodeV1[],
  positions: Record<string, LayoutPosition>,
): Record<string, LayoutPosition> {
  const next: Record<string, LayoutPosition> = {};
  for (const node of nodes) {
    const position = positions[node.id];
    if (position) {
      next[node.id] = position;
    }
  }
  return next;
}

export function strongestNeighborSeeds(
  nodes: GraphNodeV1[],
  edges: GraphEdgeV1[],
  existingPositions: Record<string, LayoutPosition>,
): Record<string, LayoutPosition> {
  const seeds = { ...existingPositions };
  const nodeSet = new Set(nodes.map((node) => node.id));

  for (const node of nodes) {
    if (seeds[node.id]) {
      continue;
    }

    let bestNeighbor: string | null = null;
    let bestWeight = -1;

    for (const edge of edges) {
      if (edge.source === node.id && nodeSet.has(edge.target) && seeds[edge.target]) {
        const weight = edge.riskContribution + edge.confidence;
        if (weight > bestWeight) {
          bestWeight = weight;
          bestNeighbor = edge.target;
        }
      }
      if (edge.target === node.id && nodeSet.has(edge.source) && seeds[edge.source]) {
        const weight = edge.riskContribution + edge.confidence;
        if (weight > bestWeight) {
          bestWeight = weight;
          bestNeighbor = edge.source;
        }
      }
    }

    if (bestNeighbor) {
      const anchor = seeds[bestNeighbor];
      if (!anchor) {
        continue;
      }
      seeds[node.id] = {
        x: anchor.x + ((node.id.length % 7) - 3) * 8,
        y: anchor.y + ((node.id.charCodeAt(0) % 5) - 2) * 8,
      };
    }
  }

  return seeds;
}
