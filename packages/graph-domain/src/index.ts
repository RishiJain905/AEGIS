export { createGraphStore, InMemoryGraphStore } from './store/graph-store';

export type { GraphStore } from './contracts/graph-store';

export {
  GraphDeltaApplyStatus,
  GraphLayer,
  type FilteredGraphView,
  type GraphConsistencyIssue,
  type GraphConsistencyReport,
  type GraphDeltaApplyResult,
  type GraphDeltaApplyStatusValue,
  type GraphFilterSet,
  type GraphLayerValue,
  type GraphPredicateFilter,
  type IncidentSubgraphOptions,
  type IncidentSubgraphResult,
  type NeighborhoodOptions,
  type NeighborhoodResult,
} from './contracts/types';

export { GraphDomainError, GraphDomainErrorCode } from './errors/graph-domain-error';
export type { GraphDomainErrorCodeValue } from './errors/graph-domain-error';

export {
  buildMediumGraphSnapshot,
  MEDIUM_GRAPH_NODE_COUNT,
  MEDIUM_GRAPH_RUN_ID,
} from './fixtures/medium-graph-snapshot';
export {
  buildStressGraphSnapshot,
  buildTargetGraphSnapshot,
  STRESS_GRAPH_RUN_ID,
  TARGET_GRAPH_NODE_COUNT,
} from './fixtures/graph-performance-snapshots';

export const GRAPH_DOMAIN_VERSION = '1.0.0' as const;
