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
  /**
   * Apply every delta a single run event produced, at that event's sequence.
   *
   * The entry point for a caller reading the run's *event* stream rather than a dedicated
   * delta channel. Two properties `applyDelta` cannot offer such a caller:
   *
   * - Consecutive graph deltas are far apart. Most run events (telemetry, alerts, agent
   *   turns, approvals) consume a sequence and mutate no graph entity, so `applyDelta`
   *   read the next real delta as a sequence gap and dropped it. Gap detection over the
   *   full stream belongs to the caller, who is the only party that sees all of it.
   * - One event can mutate several entities. Those deltas share its sequence and must all
   *   land, rather than the first one closing the door on its siblings.
   *
   * `sequence` is the event's; deltas at or below the cursor are still refused as
   * duplicates, and per-entity revision staleness is still enforced.
   */
  applyEventDeltas(sequence: number, deltas: readonly GraphDeltaV1[]): GraphDeltaApplyResult[];
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
