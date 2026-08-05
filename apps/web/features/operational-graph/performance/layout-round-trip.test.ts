import { buildTargetGraphSnapshot, createGraphStore, GraphLayer } from '@aegis/graph-domain';
import { describe, expect, it } from 'vitest';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import type { GraphFilterSet } from '@aegis/graph-domain';

import {
  LayoutWorkerResultStatus,
  type LayoutWorkerRequest,
  type LayoutWorkerResult,
} from '@/features/operational-graph/contracts/layout-worker-protocol';
import { runForceAtlas2 } from '../../../workers/layout/force-atlas2-runner';
import { LayoutCoordinator } from './layout-coordinator';
import type { LayoutWorkerClient } from './layout-worker-client';

const FILTER_SET: GraphFilterSet = {
  enabledLayers: [
    GraphLayer.INFRASTRUCTURE,
    GraphLayer.ACTIVITY,
    GraphLayer.SECURITY_STATE,
    GraphLayer.INVESTIGATION,
    GraphLayer.PRESENTATION,
  ],
} as GraphFilterSet;

/** A board-sized slice of the target snapshot: 48 assets across 8 zones. */
function buildSnapshot(nodeCount = 48, clusterCount = 8): GraphSnapshotV1 {
  const base = buildTargetGraphSnapshot();
  const nodes = base.nodes.slice(0, nodeCount).map((node, index) => ({
    ...node,
    clusterId: `business-unit:cluster-${String(index % clusterCount).padStart(2, '0')}`,
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const membersByCluster = new Map<string, string[]>();
  for (const node of nodes) {
    const members = membersByCluster.get(node.clusterId) ?? [];
    members.push(node.id);
    membersByCluster.set(node.clusterId, members);
  }

  return {
    ...base,
    nodes,
    edges: base.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    clusters: [...membersByCluster.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([id, memberNodeIds]) => ({
        schemaVersion: 1 as const,
        id,
        label: `Cluster ${id.split(':').at(-1) ?? id}`,
        memberNodeIds,
        revision: 1,
      })),
  };
}

/** Worker client double running the real ForceAtlas2 pass synchronously. */
function makeWorkerClient(): { client: LayoutWorkerClient; requests: LayoutWorkerRequest[] } {
  const requests: LayoutWorkerRequest[] = [];
  let handler: ((result: LayoutWorkerResult) => void) | undefined;
  const client = {
    initialize: (onMessage: (result: LayoutWorkerResult) => void) => {
      handler = onMessage;
      return Promise.resolve();
    },
    runLayout: (request: LayoutWorkerRequest) => {
      requests.push(request);
      const { positions, iterationsCompleted } = runForceAtlas2(request, () => false);
      handler?.({
        protocolVersion: 1,
        requestId: request.requestId,
        graphRevision: request.graphRevision,
        status: LayoutWorkerResultStatus.COMPLETE,
        positions,
        iterationsCompleted,
        durationMs: 1,
      } as LayoutWorkerResult);
    },
    cancel: () => undefined,
    shutdown: () => undefined,
    isResultTerminal: () => true,
  } as unknown as LayoutWorkerClient;
  return { client, requests };
}

async function mountCoordinator(
  initialPositions?: Record<string, { x: number; y: number }>,
): Promise<{
  coordinator: LayoutCoordinator;
  requests: LayoutWorkerRequest[];
  positions: () => Record<string, { x: number; y: number }>;
}> {
  const { client, requests } = makeWorkerClient();
  let latest: Record<string, { x: number; y: number }> = {};
  const coordinator = new LayoutCoordinator({
    workerClient: client,
    initialPositions,
    onPositionsUpdated: (next) => {
      latest = { ...next };
    },
  });
  await coordinator.initialize();
  return { coordinator, requests, positions: () => latest };
}

describe('layout across a 2D/3D/2D round trip', () => {
  it('hands the settled layout back unchanged instead of relaying out', async () => {
    const snapshot = buildSnapshot();
    const store = createGraphStore();
    store.loadSnapshot(snapshot);

    // Mount 1: fresh 2D. No prior layout, so a full pass runs.
    const first = await mountCoordinator();
    first.coordinator.scheduleLayout(store, FILTER_SET, []);
    const settled = first.positions();
    expect(first.requests).toHaveLength(1);
    expect(Object.keys(settled)).toHaveLength(snapshot.nodes.length);

    // Switch to 3D: the view unmounts and takes its coordinator with it.
    first.coordinator.dispose();

    // Back to 2D: the visual store still holds the settled layout.
    const second = await mountCoordinator(settled);
    second.coordinator.scheduleLayout(store, FILTER_SET, []);

    expect(second.requests).toHaveLength(0);
    expect(second.positions()).toEqual(settled);
  });

  it('still lays out when nodes arrived while the 3D view was up', async () => {
    const before = buildSnapshot(36);
    const after = buildSnapshot(48);
    const store = createGraphStore();
    store.loadSnapshot(before);

    const first = await mountCoordinator();
    first.coordinator.scheduleLayout(store, FILTER_SET, []);
    const settled = first.positions();
    first.coordinator.dispose();

    // Twelve assets were disclosed while the operator was in the 3D theater,
    // so the restored layout no longer covers the board.
    store.loadSnapshot(after);

    const second = await mountCoordinator(settled);
    second.coordinator.scheduleLayout(store, FILTER_SET, []);

    expect(second.requests).toHaveLength(1);
    expect(Object.keys(second.positions())).toHaveLength(after.nodes.length);
  });

  it('lays out normally when the restored layout is empty', async () => {
    const snapshot = buildSnapshot();
    const store = createGraphStore();
    store.loadSnapshot(snapshot);

    const mounted = await mountCoordinator({});
    mounted.coordinator.scheduleLayout(store, FILTER_SET, []);

    expect(mounted.requests).toHaveLength(1);
  });
});
