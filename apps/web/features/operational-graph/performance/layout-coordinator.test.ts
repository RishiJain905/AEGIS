import { createGraphStore, buildTargetGraphSnapshot, GraphLayer } from '@aegis/graph-domain';
import { describe, expect, it, vi } from 'vitest';

import {
  LayoutWorkerResultStatus,
  type LayoutWorkerResult,
} from '@/features/operational-graph/contracts/layout-worker-protocol';
import { graphRevisionFromSnapshot } from '@/features/operational-graph/contracts/graph-revision';
import { LayoutCoordinator } from './layout-coordinator';
import { LayoutWorkerClient } from './layout-worker-client';

describe('layout coordinator', () => {
  it('drops stale worker results', async () => {
    const snapshot = buildTargetGraphSnapshot();
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const revision = graphRevisionFromSnapshot(snapshot);

    let handler: ((result: LayoutWorkerResult) => void) | undefined;
    const workerClient = {
      initialize: vi.fn((onMessage: (result: LayoutWorkerResult) => void) => {
        handler = onMessage;
        return Promise.resolve();
      }),
      runLayout: vi.fn(),
      cancel: vi.fn(),
      shutdown: vi.fn(),
      isResultTerminal: (status: LayoutWorkerResult['status']) =>
        status === LayoutWorkerResultStatus.COMPLETE ||
        status === LayoutWorkerResultStatus.CANCELLED ||
        status === LayoutWorkerResultStatus.ERROR,
    } as unknown as LayoutWorkerClient;

    const coordinator = new LayoutCoordinator({ workerClient });
    await coordinator.initialize();
    coordinator.scheduleLayout(
      store,
      {
        enabledLayers: [
          GraphLayer.INFRASTRUCTURE,
          GraphLayer.ACTIVITY,
          GraphLayer.SECURITY_STATE,
          GraphLayer.INVESTIGATION,
          GraphLayer.PRESENTATION,
        ],
      },
      [],
    );

    const staleResult: LayoutWorkerResult = {
      protocolVersion: 1,
      requestId: 'stale',
      graphRevision: { ...revision, revision: revision.revision + 5 },
      status: LayoutWorkerResultStatus.COMPLETE,
      positions: { 'asset:target-00000': { x: 9, y: 9 } },
      iterationsCompleted: 1,
      durationMs: 1,
    };

    handler?.(staleResult);
    expect(coordinator.getPositions()['asset:target-00000']).toBeUndefined();
    coordinator.dispose();
  });
});
