import { describe, expect, it } from 'vitest';

import { defaultGraphBenchmarkManifest, getBenchmarkDataset } from './benchmark-manifest';
import { createGraphPerformanceSample } from './graph-performance-sample';
import { graphRevisionFromSnapshot } from './graph-revision';
import {
  defaultLayoutWorkerSettings,
  LayoutWorkerResultStatus,
  layoutWorkerRequestSchema,
  layoutWorkerResultSchema,
  parseLayoutWorkerRequest,
} from './layout-worker-protocol';
import { defaultLodPolicy, resolveLodTier } from './lod-policy';
import { defaultGraphVisualState } from './graph-visual-state';

describe('Phase 07 contracts', () => {
  it('parses layout worker request and result', () => {
    const request = parseLayoutWorkerRequest({
      protocolVersion: 1,
      requestId: 'req-1',
      graphRevision: {
        schemaVersion: 1,
        runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        sequence: 1,
        revision: 1,
      },
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      mode: 'full',
      nodes: [{ id: 'asset:a', clusterId: null, pinned: false }],
      edges: [],
      seedPositions: {},
      settings: defaultLayoutWorkerSettings,
    });

    expect(layoutWorkerRequestSchema.parse(request).requestId).toBe('req-1');

    const result = layoutWorkerResultSchema.parse({
      protocolVersion: 1,
      requestId: 'req-1',
      graphRevision: request.graphRevision,
      status: LayoutWorkerResultStatus.COMPLETE,
      positions: { 'asset:a': { x: 1, y: 2 } },
      iterationsCompleted: 10,
      durationMs: 5,
    });

    expect(result.positions?.['asset:a']).toEqual({ x: 1, y: 2 });
  });

  it('resolves LOD tiers by density', () => {
    const detail = resolveLodTier(defaultLodPolicy, 50, 80);
    const dense = resolveLodTier(defaultLodPolicy, 2000, 4000);

    expect(detail.id).toBe('detail');
    expect(dense.id).toBe('dense');
  });

  it('creates performance samples and benchmark manifest entries', () => {
    const sample = createGraphPerformanceSample({
      frameTimeMs: 12,
      syncLatencyMs: 4,
      workerDurationMs: 120,
      visibleNodes: 500,
      visibleEdges: 900,
      lodTier: 'balanced',
      droppedFrames: 0,
      droppedWorkerResults: 0,
    });

    expect(sample.schemaVersion).toBe(1);
    expect(getBenchmarkDataset(defaultGraphBenchmarkManifest, 'target').nodeCount).toBe(500);
  });

  it('derives graph revision from snapshot', () => {
    const revision = graphRevisionFromSnapshot({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sequence: 10,
      revision: 3,
      capturedAt: '2026-06-30T00:00:00.000Z',
      nodes: [],
      edges: [],
      clusters: [],
    });

    expect(revision.sequence).toBe(10);
    expect(revision.revision).toBe(3);
  });

  it('includes Phase 07 visual state fields', () => {
    expect(defaultGraphVisualState.pinnedNodeIds).toEqual([]);
    expect(defaultGraphVisualState.collapsedClusterIds).toEqual([]);
    expect(defaultGraphVisualState.layoutStatus).toBe('idle');
  });
});
