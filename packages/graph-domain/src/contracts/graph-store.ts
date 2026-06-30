import type {
  GraphClusterV1,
  GraphDeltaV1,
  GraphPathQueryV1,
  GraphPathResultV1,
  GraphSnapshotV1,
} from '@aegis/contracts-ts';

import type {
  FilteredGraphView,
  GraphConsistencyReport,
  GraphDeltaApplyResult,
  GraphFilterSet,
  IncidentSubgraphOptions,
  IncidentSubgraphResult,
  NeighborhoodOptions,
  NeighborhoodResult,
} from './types';

export interface GraphStore {
  loadSnapshot(snapshot: GraphSnapshotV1): void;
  applyDelta(delta: GraphDeltaV1): GraphDeltaApplyResult;
  applyDeltas(deltas: GraphDeltaV1[]): GraphDeltaApplyResult[];
  exportSnapshot(): GraphSnapshotV1;
  validateConsistency(): GraphConsistencyReport;
  queryPaths(query: GraphPathQueryV1): GraphPathResultV1;
  getNeighborhood(nodeId: string, options: NeighborhoodOptions): NeighborhoodResult;
  getIncidentSubgraph(
    seedNodeIds: string[],
    options?: IncidentSubgraphOptions,
  ): IncidentSubgraphResult;
  getConnectedComponents(): string[][];
  getClusterMembers(clusterId: string): string[];
  getClusters(): GraphClusterV1[];
  getDependencies(nodeId: string, maxDepth?: number): string[];
  applyFilters(filterSet: GraphFilterSet): FilteredGraphView;
  getRunId(): string | null;
  getLastAppliedSequence(): number;
  getSnapshotRevision(): number;
  clear(): void;
}
