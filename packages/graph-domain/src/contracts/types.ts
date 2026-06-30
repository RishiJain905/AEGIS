import type { GraphDomainErrorCodeValue } from '../errors/graph-domain-error';

export const GraphDeltaApplyStatus = {
  APPLIED: 'applied',
  DUPLICATE: 'duplicate',
  REJECTED: 'rejected',
  GAP_DETECTED: 'gap_detected',
} as const;

export type GraphDeltaApplyStatusValue =
  (typeof GraphDeltaApplyStatus)[keyof typeof GraphDeltaApplyStatus];

export interface GraphDeltaApplyResult {
  status: GraphDeltaApplyStatusValue;
  sequence: number;
  revision: number;
  operation: string;
  errorCode?: GraphDomainErrorCodeValue;
  message?: string;
}

export interface NeighborhoodOptions {
  hops: number;
  relationshipTypes?: string[];
  directedOnly?: boolean;
  includeCenter?: boolean;
}

export interface NeighborhoodResult {
  centerNodeId: string;
  hops: number;
  nodeIds: string[];
  edgeIds: string[];
  hopRings: string[][];
  explanation: Record<string, unknown>;
}

export interface IncidentSubgraphOptions {
  hops?: number;
  relationshipTypes?: string[];
  directedOnly?: boolean;
}

export interface IncidentSubgraphResult {
  seedNodeIds: string[];
  nodeIds: string[];
  edgeIds: string[];
  boundaryEdgeIds: string[];
  explanation: Record<string, unknown>;
}

export interface GraphConsistencyIssue {
  code: string;
  message: string;
  entityId?: string;
  details?: Record<string, unknown>;
}

export interface GraphConsistencyReport {
  valid: boolean;
  issues: GraphConsistencyIssue[];
  nodeCount: number;
  edgeCount: number;
  clusterCount: number;
}

export const GraphLayer = {
  INFRASTRUCTURE: 'infrastructure',
  ACTIVITY: 'activity',
  SECURITY_STATE: 'security_state',
  INVESTIGATION: 'investigation',
  PRESENTATION: 'presentation',
} as const;

export type GraphLayerValue = (typeof GraphLayer)[keyof typeof GraphLayer];

export interface GraphPredicateFilter {
  nodeStatuses?: string[];
  minRiskScore?: number;
  relationshipTypes?: string[];
  assetTypes?: string[];
}

export interface GraphFilterSet {
  enabledLayers: GraphLayerValue[];
  hiddenNodeIds?: string[];
  hiddenEdgeIds?: string[];
  predicate?: GraphPredicateFilter;
}

export interface FilteredGraphView {
  visibleNodeIds: string[];
  visibleEdgeIds: string[];
  hiddenNodeCount: number;
  hiddenEdgeCount: number;
  appliedLayers: GraphLayerValue[];
}
