import { GraphLayer } from '@aegis/graph-domain';

/**
 * Client-side layer emphasis over the canonical snapshot.
 *
 * The domain layer filter (`applyFiltersOnGraph`) decides hard visibility, but
 * its union semantics make individual toggles invisible while the
 * PRESENTATION layer (which matches every node) is enabled. This module mirrors
 * the domain's layer-membership rules — with PRESENTATION scoped to cluster
 * presentation entities only — and reports which visible nodes/edges belong to
 * **no enabled layer** so the renderers can dim them. Toggling any layer off
 * therefore always has a visible de-emphasis effect without diverging from the
 * domain contract's visibility decisions.
 */
export interface LayerEmphasis {
  dimmedNodeIds: Set<string>;
  dimmedEdgeIds: Set<string>;
}

const INFRASTRUCTURE_ASSET_TYPES = new Set(['service', 'device', 'database', 'control']);

const INVESTIGATION_STATUSES = new Set([
  'suspicious',
  'under_investigation',
  'contained',
  'compromised',
]);

type EmphasisSnapshot = {
  nodes: readonly {
    id: string;
    entityType: string;
    assetType: string;
    riskScore: number;
    status: string;
  }[];
  edges: readonly {
    id: string;
    source: string;
    target: string;
    eventCount: number;
    riskContribution: number;
  }[];
};

function nodeLayers(node: EmphasisSnapshot['nodes'][number], hasActiveEdge: boolean): Set<string> {
  const layers = new Set<string>();
  if (INFRASTRUCTURE_ASSET_TYPES.has(node.assetType)) {
    layers.add(GraphLayer.INFRASTRUCTURE);
  }
  if (hasActiveEdge) {
    layers.add(GraphLayer.ACTIVITY);
  }
  if (node.riskScore > 0 || node.status !== 'normal') {
    layers.add(GraphLayer.SECURITY_STATE);
  }
  if (INVESTIGATION_STATUSES.has(node.status)) {
    layers.add(GraphLayer.INVESTIGATION);
  }
  if (node.entityType === 'cluster') {
    layers.add(GraphLayer.PRESENTATION);
  }
  // Identity-plane assets (user/identity/ai_model) with no other signal still
  // belong to the base infrastructure plane for emphasis purposes; otherwise
  // they would be dimmed even with every layer enabled.
  if (layers.size === 0) {
    layers.add(GraphLayer.INFRASTRUCTURE);
  }
  return layers;
}

function edgeLayers(
  edge: EmphasisSnapshot['edges'][number],
  investigationEndpoints: ReadonlySet<string>,
): Set<string> {
  const layers = new Set<string>();
  if (edge.eventCount === 0) {
    layers.add(GraphLayer.INFRASTRUCTURE);
  }
  if (edge.eventCount > 0) {
    layers.add(GraphLayer.ACTIVITY);
  }
  if (edge.riskContribution > 0) {
    layers.add(GraphLayer.SECURITY_STATE);
  }
  if (investigationEndpoints.has(edge.source) || investigationEndpoints.has(edge.target)) {
    layers.add(GraphLayer.INVESTIGATION);
  }
  return layers;
}

export function computeLayerEmphasis(
  snapshot: EmphasisSnapshot,
  enabledLayers: readonly string[],
): LayerEmphasis {
  const enabled = new Set(enabledLayers);
  const dimmedNodeIds = new Set<string>();
  const dimmedEdgeIds = new Set<string>();

  const activeEdgeEndpoints = new Set<string>();
  for (const edge of snapshot.edges) {
    if (edge.eventCount > 0) {
      activeEdgeEndpoints.add(edge.source);
      activeEdgeEndpoints.add(edge.target);
    }
  }

  const investigationEndpoints = new Set<string>();
  for (const node of snapshot.nodes) {
    if (INVESTIGATION_STATUSES.has(node.status)) {
      investigationEndpoints.add(node.id);
    }
    const layers = nodeLayers(node, activeEdgeEndpoints.has(node.id));
    if (![...layers].some((layer) => enabled.has(layer))) {
      dimmedNodeIds.add(node.id);
    }
  }

  for (const edge of snapshot.edges) {
    const layers = edgeLayers(edge, investigationEndpoints);
    const memberOfEnabled = [...layers].some((layer) => enabled.has(layer));
    if (!memberOfEnabled || dimmedNodeIds.has(edge.source) || dimmedNodeIds.has(edge.target)) {
      dimmedEdgeIds.add(edge.id);
    }
  }

  return { dimmedNodeIds, dimmedEdgeIds };
}
