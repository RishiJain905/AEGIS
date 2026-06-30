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

export const GRAPH_DOMAIN_VERSION = '0.0.0-phase05' as const;
