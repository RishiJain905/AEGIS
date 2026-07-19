import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';

import {
  getNodeSemanticAccent,
  getNodeShape,
  getNodeSizeTier,
  getNodeVisualStyle,
  getRiskHaloColor,
  resolveEdgeFlowStyle,
  resolveEdgeSemanticStyle,
  type EdgeHighlightKind,
} from '@/features/operational-graph/semantic/graph-semantic-styles';
import { NO_PULSE } from '@/features/operational-graph/semantic/edge-activity';
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

/**
 * §7.6 risk-skyline altitude: the ground plane carries the 2D layout (scene
 * X/Z stay synced to the operational graph's X/Y), and only the node's height
 * above the plane is derived — client-side, at render time — from its risk
 * score. Modest range so the scene reads as a skyline, not a tower.
 */
const RISK_ALTITUDE_BASE = 24;
const RISK_ALTITUDE_RANGE = 150;

export function riskAltitude(riskScore: number): number {
  return RISK_ALTITUDE_BASE + Math.min(1, Math.max(0, riskScore)) * RISK_ALTITUDE_RANGE;
}

export function highlightKindForMode(
  mode: GraphVisualState['highlightMode'],
): EdgeHighlightKind | null {
  switch (mode) {
    case GraphHighlightMode.NEIGHBORHOOD:
      return 'neighborhood';
    case GraphHighlightMode.PATH:
      return 'path';
    case GraphHighlightMode.INCIDENT:
      return 'incident';
    case GraphHighlightMode.DEPENDENCIES:
      return 'dependencies';
    case GraphHighlightMode.NONE:
      return null;
    default: {
      const _exhaustive: never = mode;
      throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
    }
  }
}

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
  const accent = getNodeSemanticAccent(node);
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
    position: {
      x: position.x,
      y: riskAltitude(node.riskScore),
      z: position.z,
    },
    color: style.color,
    statusColor:
      visualState.overlayToggles.status && node.status !== 'normal'
        ? style.statusColor
        : 'transparent',
    riskHaloColor:
      visualState.overlayToggles.risk && riskEmphasized
        ? getRiskHaloColor(style.riskBand)
        : 'transparent',
    emissiveColor: accent.emissiveColor,
    sizeTier: getNodeSizeTier(node.assetType),
    glyphShape: getNodeShape(node.assetType),
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
  /** Shared-animation-clock timestamp of the edge's last live-event pulse. */
  pulseAt?: number;
}): SceneEdge {
  const { edge, visualState, layerDimmed = false, pulseAt = NO_PULSE } = input;
  const highlightEdges = new Set(visualState.highlightedEdgeIds);
  const highlightNodes = new Set(visualState.highlightedNodeIds);
  const isHighlighted = highlightEdges.has(edge.id);
  const isIsolation = visualState.isolationActive && highlightNodes.size > 0;
  const isDimmed = (isIsolation || layerDimmed) && !isHighlighted;

  const semantic = resolveEdgeSemanticStyle({
    edge,
    highlighted: isHighlighted,
    dimmed: isDimmed,
    highlightKind: highlightKindForMode(visualState.highlightMode),
  });
  const flow = resolveEdgeFlowStyle({
    directed: edge.directed,
    highlighted: isHighlighted,
    dimmed: isDimmed,
  });

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
    color: isDimmed ? '#94a3b866' : semantic.color,
    opacity: semantic.opacity,
    width: semantic.width,
    highlighted: isHighlighted,
    dimmed: isDimmed,
    dashed: semantic.dashed,
    flowSpeed: flow?.speed ?? 0,
    flowAmplitude: flow?.amplitude ?? 0,
    pulseAt,
  };
}
