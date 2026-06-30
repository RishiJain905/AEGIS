import { AssetType, NodeStatus } from '@aegis/contracts-ts';

import {
  EDGE_ATTR_KEY,
  getNodeCanonical,
  type CanonicalGraph,
} from '../adapters/canonical-graphology';
import {
  GraphLayer,
  type FilteredGraphView,
  type GraphFilterSet,
  type GraphLayerValue,
} from '../contracts/types';

const INFRASTRUCTURE_ASSET_TYPES = new Set<string>([
  AssetType.SERVICE,
  AssetType.DEVICE,
  AssetType.DATABASE,
  AssetType.CONTROL,
]);

const INVESTIGATION_STATUSES = new Set<string>([
  NodeStatus.SUSPICIOUS,
  NodeStatus.UNDER_INVESTIGATION,
  NodeStatus.CONTAINED,
  NodeStatus.COMPROMISED,
]);

function nodeMatchesLayer(graph: CanonicalGraph, nodeId: string, layer: GraphLayerValue): boolean {
  const node = getNodeCanonical(graph, nodeId);
  if (node === undefined) {
    return false;
  }

  switch (layer) {
    case GraphLayer.INFRASTRUCTURE:
      return INFRASTRUCTURE_ASSET_TYPES.has(node.assetType);
    case GraphLayer.ACTIVITY:
      return graph.someEdge(nodeId, (_edge, attributes) => {
        return attributes[EDGE_ATTR_KEY].eventCount > 0;
      });
    case GraphLayer.SECURITY_STATE:
      return node.riskScore > 0 || node.status !== NodeStatus.NORMAL;
    case GraphLayer.INVESTIGATION:
      return INVESTIGATION_STATUSES.has(node.status);
    case GraphLayer.PRESENTATION:
      return true;
    default: {
      const exhaustive: never = layer;
      return exhaustive;
    }
  }
}

function edgeMatchesLayer(graph: CanonicalGraph, edgeId: string, layer: GraphLayerValue): boolean {
  const edge = graph.getEdgeAttributes(edgeId)[EDGE_ATTR_KEY];
  const source = graph.source(edgeId);
  const target = graph.target(edgeId);

  switch (layer) {
    case GraphLayer.INFRASTRUCTURE:
      return nodeMatchesLayer(graph, source, layer) && nodeMatchesLayer(graph, target, layer);
    case GraphLayer.ACTIVITY:
      return edge.eventCount > 0;
    case GraphLayer.SECURITY_STATE:
      return edge.riskContribution > 0;
    case GraphLayer.INVESTIGATION:
      return (
        nodeMatchesLayer(graph, source, GraphLayer.INVESTIGATION) ||
        nodeMatchesLayer(graph, target, GraphLayer.INVESTIGATION)
      );
    case GraphLayer.PRESENTATION:
      return true;
    default: {
      const exhaustive: never = layer;
      return exhaustive;
    }
  }
}

function nodeMatchesPredicate(
  graph: CanonicalGraph,
  nodeId: string,
  filterSet: GraphFilterSet,
): boolean {
  const predicate = filterSet.predicate;
  if (predicate === undefined) {
    return true;
  }

  const node = getNodeCanonical(graph, nodeId);
  if (node === undefined) {
    return false;
  }

  if (
    predicate.nodeStatuses !== undefined &&
    predicate.nodeStatuses.length > 0 &&
    !predicate.nodeStatuses.includes(node.status)
  ) {
    return false;
  }

  if (predicate.minRiskScore !== undefined && node.riskScore < predicate.minRiskScore) {
    return false;
  }

  if (
    predicate.assetTypes !== undefined &&
    predicate.assetTypes.length > 0 &&
    !predicate.assetTypes.includes(node.assetType)
  ) {
    return false;
  }

  void graph;
  return true;
}

function edgeMatchesPredicate(
  graph: CanonicalGraph,
  edgeId: string,
  filterSet: GraphFilterSet,
): boolean {
  const predicate = filterSet.predicate;
  if (predicate === undefined || predicate.relationshipTypes === undefined) {
    return true;
  }
  if (predicate.relationshipTypes.length === 0) {
    return true;
  }
  const edge = graph.getEdgeAttributes(edgeId)[EDGE_ATTR_KEY];
  return predicate.relationshipTypes.includes(edge.relationshipType);
}

export function applyFiltersOnGraph(
  graph: CanonicalGraph,
  filterSet: GraphFilterSet,
): FilteredGraphView {
  const hiddenNodes = new Set(filterSet.hiddenNodeIds ?? []);
  const hiddenEdges = new Set(filterSet.hiddenEdgeIds ?? []);
  const enabledLayers = new Set(filterSet.enabledLayers);

  const visibleNodeIds: string[] = [];
  const visibleEdgeIds: string[] = [];

  graph.forEachNode((nodeId) => {
    if (hiddenNodes.has(nodeId)) {
      return;
    }

    const layerVisible = [...enabledLayers].some((layer) => nodeMatchesLayer(graph, nodeId, layer));
    if (!layerVisible) {
      return;
    }

    if (!nodeMatchesPredicate(graph, nodeId, filterSet)) {
      return;
    }

    visibleNodeIds.push(nodeId);
  });

  const visibleNodeSet = new Set(visibleNodeIds);

  graph.forEachEdge((edgeId, _attrs, source, target) => {
    if (hiddenEdges.has(edgeId)) {
      return;
    }
    if (!visibleNodeSet.has(source) || !visibleNodeSet.has(target)) {
      return;
    }

    const layerVisible = [...enabledLayers].some((layer) => edgeMatchesLayer(graph, edgeId, layer));
    if (!layerVisible) {
      return;
    }

    if (!edgeMatchesPredicate(graph, edgeId, filterSet)) {
      return;
    }

    visibleEdgeIds.push(edgeId);
  });

  visibleNodeIds.sort((a, b) => a.localeCompare(b));
  visibleEdgeIds.sort((a, b) => a.localeCompare(b));

  return {
    visibleNodeIds,
    visibleEdgeIds,
    hiddenNodeCount: graph.order - visibleNodeIds.length,
    hiddenEdgeCount: graph.size - visibleEdgeIds.length,
    appliedLayers: [...filterSet.enabledLayers],
  };
}
