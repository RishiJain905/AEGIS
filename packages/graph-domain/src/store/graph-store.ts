import type {
  GraphClusterV1,
  GraphDeltaV1,
  GraphPathQueryV1,
  GraphPathResultV1,
  GraphSnapshotV1,
} from '@aegis/contracts-ts';
import { graphPathQuerySchema, graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';

import {
  createEmptyGraph,
  exportGraphToSnapshot,
  loadSnapshotIntoGraph,
  type CanonicalGraph,
} from '../adapters/canonical-graphology';
import { queryPathsOnGraph } from '../algorithms/paths';
import {
  getClusterMembersFromMap,
  getConnectedComponentsOnGraph,
  getDependenciesOnGraph,
  getIncidentSubgraphOnGraph,
  getNeighborhoodOnGraph,
} from '../algorithms/neighborhoods';
import type { GraphStore } from '../contracts/graph-store';
import type {
  FilteredGraphView,
  GraphConsistencyReport,
  GraphDeltaApplyResult,
  GraphFilterSet,
  IncidentSubgraphOptions,
  IncidentSubgraphResult,
  NeighborhoodOptions,
  NeighborhoodResult,
} from '../contracts/types';
import { applyDeltaToContext, type DeltaApplicationContext } from '../delta/apply-delta';
import { applyFiltersOnGraph } from '../filtering/layer-filter';
import { validateGraphConsistency } from '../lifecycle/consistency';

export class InMemoryGraphStore implements GraphStore {
  private graph: CanonicalGraph = createEmptyGraph();
  private clusters = new Map<string, GraphClusterV1>();
  private runId: string | null = null;
  private lastAppliedSequence = 0;
  private snapshotRevision = 0;
  private capturedAt = new Date(0).toISOString();

  loadSnapshot(snapshot: GraphSnapshotV1): void {
    const validated = parseContract(graphSnapshotSchema, snapshot);
    this.graph = createEmptyGraph();
    this.clusters = loadSnapshotIntoGraph(this.graph, validated);
    this.runId = validated.runId;
    this.lastAppliedSequence = validated.sequence;
    this.snapshotRevision = validated.revision;
    this.capturedAt = validated.capturedAt;
  }

  applyDelta(delta: GraphDeltaV1): GraphDeltaApplyResult {
    if (this.runId === null) {
      throw new Error('GraphStore has no loaded snapshot');
    }
    const ctx = this.createContext();
    const result = applyDeltaToContext(ctx, delta);
    this.syncFromContext(ctx);
    return result;
  }

  applyEventDeltas(sequence: number, deltas: readonly GraphDeltaV1[]): GraphDeltaApplyResult[] {
    if (this.runId === null) {
      throw new Error('GraphStore has no loaded snapshot');
    }
    if (deltas.length === 0) {
      this.lastAppliedSequence = Math.max(this.lastAppliedSequence, sequence);
      return [];
    }
    const cursorBefore = this.lastAppliedSequence;
    const results: GraphDeltaApplyResult[] = [];
    for (const delta of deltas) {
      // Every delta of one event occupies that event's position, so each is judged against
      // the cursor as it stood *before* the event. Letting the first advance the cursor
      // made each later sibling look like a duplicate of itself, which is how a risk
      // projection covering four assets only ever moved the first one.
      const ctx = this.createContext();
      ctx.lastAppliedSequence = cursorBefore;
      ctx.enforceContiguity = false;
      results.push(applyDeltaToContext(ctx, { ...delta, sequence }));
      this.syncFromContext(ctx);
    }
    this.lastAppliedSequence = Math.max(cursorBefore, sequence);
    return results;
  }

  applyDeltas(deltas: GraphDeltaV1[]): GraphDeltaApplyResult[] {
    const results: GraphDeltaApplyResult[] = [];
    for (const delta of deltas) {
      const result = this.applyDelta(delta);
      results.push(result);
      if (result.status !== 'applied' && result.status !== 'duplicate') {
        break;
      }
    }
    return results;
  }

  exportSnapshot(): GraphSnapshotV1 {
    if (this.runId === null) {
      throw new Error('GraphStore has no loaded snapshot');
    }
    return exportGraphToSnapshot(this.graph, this.clusters, {
      runId: this.runId,
      sequence: this.lastAppliedSequence,
      capturedAt: this.capturedAt,
      revision: this.snapshotRevision,
    });
  }

  validateConsistency(): GraphConsistencyReport {
    return validateGraphConsistency(this.graph, this.clusters);
  }

  queryPaths(query: GraphPathQueryV1): GraphPathResultV1 {
    const validated = parseContract(graphPathQuerySchema, query);
    if (this.runId !== null && validated.runId !== this.runId) {
      throw new Error(
        `Path query runId ${validated.runId} does not match store runId ${this.runId}`,
      );
    }
    return queryPathsOnGraph(this.graph, validated);
  }

  getNeighborhood(nodeId: string, options: NeighborhoodOptions): NeighborhoodResult {
    return getNeighborhoodOnGraph(this.graph, nodeId, options);
  }

  getIncidentSubgraph(
    seedNodeIds: string[],
    options: IncidentSubgraphOptions = {},
  ): IncidentSubgraphResult {
    return getIncidentSubgraphOnGraph(this.graph, seedNodeIds, options);
  }

  getConnectedComponents(): string[][] {
    return getConnectedComponentsOnGraph(this.graph);
  }

  getClusterMembers(clusterId: string): string[] {
    return getClusterMembersFromMap(this.clusters, clusterId);
  }

  getClusters(): GraphClusterV1[] {
    return [...this.clusters.values()].sort((a, b) => a.id.localeCompare(b.id));
  }

  getDependencies(nodeId: string, maxDepth = 8): string[] {
    return getDependenciesOnGraph(this.graph, nodeId, maxDepth);
  }

  applyFilters(filterSet: GraphFilterSet): FilteredGraphView {
    return applyFiltersOnGraph(this.graph, filterSet);
  }

  getRunId(): string | null {
    return this.runId;
  }

  getLastAppliedSequence(): number {
    return this.lastAppliedSequence;
  }

  getSnapshotRevision(): number {
    return this.snapshotRevision;
  }

  clear(): void {
    this.graph = createEmptyGraph();
    this.clusters.clear();
    this.runId = null;
    this.lastAppliedSequence = 0;
    this.snapshotRevision = 0;
    this.capturedAt = new Date(0).toISOString();
  }

  private createContext(): DeltaApplicationContext {
    if (this.runId === null) {
      throw new Error('GraphStore has no loaded snapshot');
    }
    return {
      graph: this.graph,
      clusters: this.clusters,
      runId: this.runId,
      lastAppliedSequence: this.lastAppliedSequence,
      snapshotRevision: this.snapshotRevision,
      capturedAt: this.capturedAt,
    };
  }

  private syncFromContext(ctx: DeltaApplicationContext): void {
    this.lastAppliedSequence = ctx.lastAppliedSequence;
    this.snapshotRevision = ctx.snapshotRevision;
    this.capturedAt = ctx.capturedAt;
  }
}

export function createGraphStore(): GraphStore {
  return new InMemoryGraphStore();
}
