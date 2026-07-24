import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

import { computeZoneLayout, type LayoutPosition } from './zone-layout';

export type { LayoutPosition } from './zone-layout';

/**
 * Deterministic first-paint layout: delegates to the zone sector board so the
 * graph is legible before (and independent of) the force worker. Existing
 * positions are preserved — during a run only genuinely new nodes are placed.
 */
export function computeInitialLayout(
  nodes: GraphNodeV1[],
  clusters: GraphClusterV1[],
  existingPositions: Record<string, LayoutPosition> = {},
): Record<string, LayoutPosition> {
  return computeZoneLayout(nodes, clusters, existingPositions).positions;
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
