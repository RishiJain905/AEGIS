import { describe, expect, it } from 'vitest';

import {
  defaultLayoutWorkerSettings,
  LayoutWorkerResultStatus,
} from '@/features/operational-graph/contracts/layout-worker-protocol';
import { runForceAtlas2 } from '@/workers/layout/force-atlas2-runner';
import { buildTargetGraphSnapshot } from '@aegis/graph-domain';
import {
  getBenchmarkDataset,
  defaultGraphBenchmarkManifest,
} from '@/features/operational-graph/contracts/benchmark-manifest';
import { graphRevisionFromSnapshot } from '@/features/operational-graph/contracts/graph-revision';

describe('graph worker layout performance', () => {
  it('completes target graph layout within budget', () => {
    const snapshot = buildTargetGraphSnapshot();
    const revision = graphRevisionFromSnapshot(snapshot);
    const startedAt = performance.now();

    const result = runForceAtlas2(
      {
        protocolVersion: 1,
        requestId: 'perf-target',
        graphRevision: revision,
        runId: snapshot.runId,
        mode: 'full',
        nodes: snapshot.nodes.map((node) => ({
          id: node.id,
          clusterId: node.clusterId ?? null,
          pinned: false,
        })),
        edges: snapshot.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          weight: edge.riskContribution + edge.confidence,
        })),
        seedPositions: {},
        settings: { ...defaultLayoutWorkerSettings, iterations: 30 },
      },
      () => false,
    );

    const elapsed = performance.now() - startedAt;
    const budget = getBenchmarkDataset(
      defaultGraphBenchmarkManifest,
      'target',
    ).workerLayoutBudgetMs;

    expect(Object.keys(result.positions).length).toBe(snapshot.nodes.length);
    expect(result.iterationsCompleted).toBeGreaterThan(0);
    expect(elapsed).toBeLessThan(budget);
  });

  it('supports cancellation during stress layout', () => {
    const snapshot = buildTargetGraphSnapshot('run_01ARZ3NDEKTSV4RRFFQ69G5FBY');
    const revision = graphRevisionFromSnapshot(snapshot);
    let calls = 0;

    const result = runForceAtlas2(
      {
        protocolVersion: 1,
        requestId: 'perf-cancel',
        graphRevision: revision,
        runId: snapshot.runId,
        mode: 'full',
        nodes: snapshot.nodes.map((node) => ({
          id: node.id,
          clusterId: node.clusterId ?? null,
          pinned: false,
        })),
        edges: snapshot.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          weight: 1,
        })),
        seedPositions: {},
        settings: { ...defaultLayoutWorkerSettings, iterations: 200 },
      },
      () => {
        calls += 1;
        return calls > 1;
      },
    );

    expect(result.iterationsCompleted).toBeLessThan(200);
  });
});
