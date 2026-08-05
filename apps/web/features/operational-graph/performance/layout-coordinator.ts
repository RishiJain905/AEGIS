import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';

import {
  graphRevisionFromSnapshot,
  graphRevisionKey,
  isSameGraphRevision,
  type GraphRevision,
} from '../contracts/graph-revision';
import {
  defaultLayoutWorkerSettings,
  LayoutWorkerResultStatus,
  type LayoutMode,
  type LayoutWorkerRequest,
  type LayoutWorkerResult,
} from '../contracts/layout-worker-protocol';
import { LayoutStatus } from '../contracts/graph-visual-state';
import { computeZoneLayout, zoneConstraintsFromLayout } from '../layout/zone-layout';
import { LayoutWorkerClient } from './layout-worker-client';
import { PerformanceInstrumentation } from './performance-instrumentation';
import { applyPinnedPositions, strongestNeighborSeeds } from './position-persistence';
import { determineRelayoutTrigger } from './relayout-triggers';

export interface LayoutCoordinatorOptions {
  workerClient?: LayoutWorkerClient;
  instrumentation?: PerformanceInstrumentation;
  onPositionsUpdated?: (positions: Record<string, { x: number; y: number }>) => void;
  onLayoutStatusChanged?: (status: LayoutStatus) => void;
  /**
   * Layout carried over from a previous mount of the same run. The coordinator
   * dies with its component, but the visual store outlives it, so a 2D/3D/2D
   * round trip would otherwise re-run a full ForceAtlas2 pass from ring seeds
   * and land the operator on a visibly reshuffled board. Seeding the settled
   * layout back in makes the round trip a no-op.
   */
  initialPositions?: Record<string, { x: number; y: number }>;
}

type LayoutStatus = (typeof LayoutStatus)[keyof typeof LayoutStatus];

let requestCounter = 0;

function nextRequestId(): string {
  requestCounter += 1;
  return `layout-req-${String(requestCounter)}`;
}

export class LayoutCoordinator {
  private readonly workerClient: LayoutWorkerClient;
  private readonly instrumentation: PerformanceInstrumentation;
  private readonly onPositionsUpdated?: LayoutCoordinatorOptions['onPositionsUpdated'];
  private readonly onLayoutStatusChanged?: LayoutCoordinatorOptions['onLayoutStatusChanged'];
  private activeRequestId: string | null = null;
  private currentRevision: GraphRevision | null = null;
  private previousVisibleNodeIds: string[] = [];
  private previousRevisionKey: string | null = null;
  private positions: Record<string, { x: number; y: number }> = {};
  private initialized = false;
  private workerDurationMs: number | null = null;

  constructor(options: LayoutCoordinatorOptions = {}) {
    this.workerClient = options.workerClient ?? new LayoutWorkerClient();
    this.instrumentation = options.instrumentation ?? new PerformanceInstrumentation();
    this.onPositionsUpdated = options.onPositionsUpdated;
    this.onLayoutStatusChanged = options.onLayoutStatusChanged;
    this.positions = { ...options.initialPositions };
  }

  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }
    await this.workerClient.initialize((result) => {
      this.handleWorkerResult(result);
    });
    this.initialized = true;
  }

  getPositions(): Record<string, { x: number; y: number }> {
    return { ...this.positions };
  }

  getInstrumentation(): PerformanceInstrumentation {
    return this.instrumentation;
  }

  getWorkerDurationMs(): number | null {
    return this.workerDurationMs;
  }

  scheduleLayout(
    store: GraphStore,
    filterSet: GraphFilterSet,
    pinnedNodeIds: string[],
    modeOverride?: LayoutMode,
  ): void {
    const snapshot = store.exportSnapshot();
    const filtered = store.applyFilters(filterSet);
    const revision = graphRevisionFromSnapshot(snapshot);
    const revisionKey = graphRevisionKey(revision);

    // A restored layout that already covers every visible node is settled by
    // definition — it is the layout the operator was looking at a moment ago.
    // Adopt it as the baseline instead of treating this as an initial load,
    // which would force a full relayout and move nodes for no reason. A node
    // that arrived while the 3D view was up leaves the set incomplete, and the
    // normal full-layout path takes over.
    if (
      this.previousRevisionKey === null &&
      filtered.visibleNodeIds.length > 0 &&
      filtered.visibleNodeIds.every((nodeId) => this.positions[nodeId] !== undefined)
    ) {
      this.previousVisibleNodeIds = filtered.visibleNodeIds;
      this.previousRevisionKey = revisionKey;
      this.currentRevision = revision;
      this.onPositionsUpdated?.(this.getPositions());
      this.onLayoutStatusChanged?.(LayoutStatus.COMPLETE);
      return;
    }

    const trigger = determineRelayoutTrigger({
      previousVisibleNodeIds: this.previousVisibleNodeIds,
      nextVisibleNodeIds: filtered.visibleNodeIds,
      previousRevisionKey: this.previousRevisionKey,
      nextRevisionKey: revisionKey,
      isInitialLoad: this.previousRevisionKey === null,
    });

    this.previousVisibleNodeIds = filtered.visibleNodeIds;
    this.previousRevisionKey = revisionKey;
    this.currentRevision = revision;

    if (trigger === 'none' && Object.keys(this.positions).length > 0) {
      return;
    }

    const mode = modeOverride ?? (trigger === 'full' ? 'full' : 'incremental');
    this.startWorkerLayout(snapshot, filtered.visibleNodeIds, pinnedNodeIds, revision, mode);
  }

  private startWorkerLayout(
    snapshot: GraphSnapshotV1,
    visibleNodeIds: string[],
    pinnedNodeIds: string[],
    revision: GraphRevision,
    mode: LayoutMode,
  ): void {
    if (!this.initialized) {
      return;
    }

    if (this.activeRequestId) {
      this.workerClient.cancel(this.activeRequestId);
    }

    const visibleNodes = snapshot.nodes.filter((node) => visibleNodeIds.includes(node.id));
    const visibleEdges = snapshot.edges.filter(
      (edge) => visibleNodeIds.includes(edge.source) && visibleNodeIds.includes(edge.target),
    );

    const zoneLayout = computeZoneLayout(visibleNodes, snapshot.clusters, this.positions);
    const seeded = strongestNeighborSeeds(visibleNodes, visibleEdges, zoneLayout.positions);
    const pinnedPositions = applyPinnedPositions(seeded, pinnedNodeIds, seeded);

    const requestId = nextRequestId();
    this.activeRequestId = requestId;
    this.onLayoutStatusChanged?.(LayoutStatus.RUNNING);

    const request: LayoutWorkerRequest = {
      protocolVersion: 1,
      requestId,
      graphRevision: revision,
      runId: snapshot.runId,
      mode,
      nodes: visibleNodes.map((node) => ({
        id: node.id,
        clusterId: node.clusterId ?? null,
        pinned: pinnedNodeIds.includes(node.id),
        x: pinnedPositions[node.id]?.x,
        y: pinnedPositions[node.id]?.y,
      })),
      edges: visibleEdges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        weight: edge.riskContribution + edge.confidence,
      })),
      seedPositions: pinnedPositions,
      zoneConstraints: zoneConstraintsFromLayout(zoneLayout.zones),
      settings:
        mode === 'full'
          ? defaultLayoutWorkerSettings
          : { ...defaultLayoutWorkerSettings, iterations: 20 },
    };

    this.workerClient.runLayout(request);
  }

  private handleWorkerResult(result: LayoutWorkerResult): void {
    if (this.activeRequestId && result.requestId !== this.activeRequestId) {
      this.instrumentation.recordDroppedWorkerResult();
      return;
    }

    if (this.currentRevision && !isSameGraphRevision(result.graphRevision, this.currentRevision)) {
      this.instrumentation.recordDroppedWorkerResult();
      return;
    }

    if (result.status === LayoutWorkerResultStatus.PROGRESS) {
      return;
    }

    if (result.status === LayoutWorkerResultStatus.COMPLETE && result.positions) {
      this.positions = { ...this.positions, ...result.positions };
      this.workerDurationMs = result.durationMs;
      this.onPositionsUpdated?.(this.positions);
      this.onLayoutStatusChanged?.(LayoutStatus.COMPLETE);
      this.activeRequestId = null;
      return;
    }

    if (result.status === LayoutWorkerResultStatus.CANCELLED) {
      this.onLayoutStatusChanged?.(LayoutStatus.IDLE);
      this.activeRequestId = null;
      return;
    }

    if (result.status === LayoutWorkerResultStatus.ERROR) {
      this.onLayoutStatusChanged?.(LayoutStatus.ERROR);
      this.activeRequestId = null;
    }
  }

  reset(): void {
    if (this.activeRequestId) {
      this.workerClient.cancel(this.activeRequestId);
      this.activeRequestId = null;
    }
    this.positions = {};
    this.previousVisibleNodeIds = [];
    this.previousRevisionKey = null;
    this.currentRevision = null;
    this.workerDurationMs = null;
    this.onLayoutStatusChanged?.(LayoutStatus.IDLE);
  }

  dispose(): void {
    this.reset();
    this.workerClient.shutdown();
    this.initialized = false;
  }
}
