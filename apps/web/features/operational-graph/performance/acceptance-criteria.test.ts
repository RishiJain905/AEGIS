import { describe, expect, it } from 'vitest';

import { graphRevisionFromSnapshot } from '@/features/operational-graph/contracts/graph-revision';
import {
  LayoutWorkerResultStatus,
  type LayoutWorkerResult,
} from '@/features/operational-graph/contracts/layout-worker-protocol';
import { determineRelayoutTrigger } from '@/features/operational-graph/performance/relayout-triggers';
import { buildLodRenderHints } from '@/features/operational-graph/performance/lod-controller';
import { buildTargetGraphSnapshot } from '@aegis/graph-domain';
import { isSameGraphRevision } from '@/features/operational-graph/contracts/graph-revision';

describe('Phase 07 acceptance criteria', () => {
  it('keeps target fixtures within documented LOD budgets', () => {
    const hints = buildLodRenderHints({
      visibleNodeIds: Array.from({ length: 500 }, (_, index) => `asset:node-${String(index)}`),
      visibleEdgeIds: Array.from({ length: 900 }, (_, index) => `edge:${String(index)}`),
      highlightedEdgeIds: [],
      collapsedClusterIds: [],
    });

    expect(hints.tierId).toBe('balanced');
    expect(hints.visibleEdgeIds.length).toBeLessThanOrEqual(1500);
  });

  it('preserves mental map by skipping relayout on filter-only changes', () => {
    const trigger = determineRelayoutTrigger({
      previousVisibleNodeIds: ['a', 'b', 'c'],
      nextVisibleNodeIds: ['a', 'b', 'c'],
      previousRevisionKey: 'run:1:1',
      nextRevisionKey: 'run:1:1',
      isInitialLoad: false,
    });

    expect(trigger).toBe('none');
  });

  it('rejects stale worker results by revision', () => {
    const snapshot = buildTargetGraphSnapshot();
    const current = graphRevisionFromSnapshot(snapshot);
    const stale: LayoutWorkerResult = {
      protocolVersion: 1,
      requestId: 'req-1',
      graphRevision: { ...current, revision: current.revision + 1 },
      status: LayoutWorkerResultStatus.COMPLETE,
      positions: { 'asset:target-00000': { x: 1, y: 2 } },
      iterationsCompleted: 10,
      durationMs: 5,
    };

    expect(isSameGraphRevision(stale.graphRevision, current)).toBe(false);
  });

  it('degrades densely while keeping selected labels available', () => {
    const hints = buildLodRenderHints({
      visibleNodeIds: Array.from({ length: 2000 }, (_, index) => `asset:node-${String(index)}`),
      visibleEdgeIds: Array.from({ length: 4000 }, (_, index) => `edge:${String(index)}`),
      highlightedEdgeIds: ['edge:1'],
      collapsedClusterIds: ['business-unit:cluster-01'],
    });

    expect(hints.tierId).toBe('dense');
    expect(hints.visibleEdgeIds).toContain('edge:1');
    expect(hints.collapsedClusterIds).toContain('business-unit:cluster-01');
  });
});
