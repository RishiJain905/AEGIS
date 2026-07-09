import type { GraphSnapshotV1, HistoricalGraphAdapterV1, ReplayStateV1 } from '@aegis/contracts-ts';
import { createGraphStore, type GraphStore } from '@aegis/graph-domain';

export function toHistoricalGraphAdapter(state: ReplayStateV1): HistoricalGraphAdapterV1 | null {
  if (!state.graph) {
    return null;
  }
  return {
    schemaVersion: 1,
    runId: state.runId,
    sequence: state.cursor.sequence,
    graphRevision: state.graph.revision,
    stateDigest: state.stateDigest,
    source: 'replay_state_graph',
    readOnly: true,
  };
}

export function loadHistoricalGraphStore(
  store: GraphStore,
  graph: GraphSnapshotV1 | null | undefined,
): void {
  if (!graph) {
    return;
  }
  store.loadSnapshot(graph);
}

export function createHistoricalGraphStore(graph?: GraphSnapshotV1 | null): GraphStore {
  const store = createGraphStore();
  if (graph) {
    store.loadSnapshot(graph);
  }
  return store;
}
