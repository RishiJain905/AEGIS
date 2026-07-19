import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';

import {
  getEdgeVisualStyle,
  getHighlightColor,
  getNodeVisualStyle,
  getRiskHaloColor,
} from '@/features/operational-graph/semantic/graph-semantic-styles';
import {
  GraphHighlightMode,
  type GraphVisualState,
} from '@/features/operational-graph/contracts/graph-visual-state';

import {
  SCENE_EDGE_SCHEMA_VERSION,
  SCENE_NODE_SCHEMA_VERSION,
  type SceneEdge,
  type SceneNode,
} from '../contracts';

export function mapCanonicalNodeToSceneNode(input: {
  node: GraphNodeV1;
  position: { x: number; y: number; z: number };
  visualState: GraphVisualState;
  evidenceMarked: boolean;
  incidentMarked: boolean;
  layerDimmed?: boolean;
}): SceneNode {
  const {
    node,
    position,
    visualState,
    evidenceMarked,
    incidentMarked,
    layerDimmed = false,
  } = input;
  const style = getNodeVisualStyle(node);
  const highlightNodes = new Set(visualState.highlightedNodeIds);
  const isHighlighted = highlightNodes.has(node.id);
  const isSelected = visualState.selection.primaryNodeId === node.id;
  const isIsolation = visualState.isolationActive && highlightNodes.size > 0;
  const isDimmed =
    (isIsolation && !isHighlighted) || (layerDimmed && !isHighlighted && !isSelected);
  // Halo only for genuinely elevated risk — a halo on every low-risk node
  // reads as noise, not signal.
  const riskEmphasized = style.riskBand === 'high' || style.riskBand === 'critical';

  return {
    schemaVersion: SCENE_NODE_SCHEMA_VERSION,
    id: node.id,
    label: node.label,
    entityType: node.entityType === 'cluster' ? 'cluster' : 'asset',
    assetType: node.assetType,
    clusterId: node.clusterId ?? null,
    riskScore: node.riskScore,
    criticality: node.criticality,
    status: node.status,
    position,
    color: style.color,
    statusColor:
      visualState.overlayToggles.status && node.status !== 'normal'
        ? style.statusColor
        : 'transparent',
    riskHaloColor:
      visualState.overlayToggles.risk && riskEmphasized
        ? getRiskHaloColor(style.riskBand)
        : 'transparent',
    size: style.size + (isSelected ? 4 : 0),
    selected: isSelected,
    highlighted: isHighlighted,
    dimmed: isDimmed,
    evidenceMarked: visualState.overlayToggles.evidence ? evidenceMarked : false,
    incidentMarked: visualState.overlayToggles.incident ? incidentMarked : false,
  };
}

export function mapCanonicalEdgeToSceneEdge(input: {
  edge: GraphEdgeV1;
  visualState: GraphVisualState;
  layerDimmed?: boolean;
}): SceneEdge {
  const { edge, visualState, layerDimmed = false } = input;
  const edgeStyle = getEdgeVisualStyle(edge);
  const highlightEdges = new Set(visualState.highlightedEdgeIds);
  const highlightNodes = new Set(visualState.highlightedNodeIds);
  const isHighlighted = highlightEdges.has(edge.id);
  const isIsolation = visualState.isolationActive && highlightNodes.size > 0;
  const isDimmed = (isIsolation || layerDimmed) && !isHighlighted;

  let color = edgeStyle.color;
  if (isHighlighted && visualState.highlightMode !== GraphHighlightMode.NONE) {
    switch (visualState.highlightMode) {
      case GraphHighlightMode.NEIGHBORHOOD:
        color = getHighlightColor('neighborhood');
        break;
      case GraphHighlightMode.PATH:
        color = getHighlightColor('path');
        break;
      case GraphHighlightMode.INCIDENT:
        color = getHighlightColor('incident');
        break;
      case GraphHighlightMode.DEPENDENCIES:
        color = getHighlightColor('dependencies');
        break;
      default: {
        const _exhaustive: never = visualState.highlightMode;
        throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
      }
    }
  }

  return {
    schemaVersion: SCENE_EDGE_SCHEMA_VERSION,
    id: edge.id,
    sourceId: edge.source,
    targetId: edge.target,
    relationshipType: edge.relationshipType,
    directed: edge.directed,
    confidence: edge.confidence,
    riskContribution: edge.riskContribution,
    eventCount: edge.eventCount,
    color: isDimmed ? '#94a3b866' : color,
    opacity: isDimmed ? 0.15 : isHighlighted ? 1 : edgeStyle.opacity,
    width: isHighlighted ? edgeStyle.size * 2 : edgeStyle.size,
    highlighted: isHighlighted,
    dimmed: isDimmed,
  };
}
