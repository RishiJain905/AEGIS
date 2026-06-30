import { createGraphStore, buildTargetGraphSnapshot, type GraphFilterSet } from '@aegis/graph-domain';
import { describe, expect, it, vi } from 'vitest';

vi.mock('sigma', () => ({
  default: class MockSigma {
    kill = vi.fn();
    refresh = vi.fn();
    setSetting = vi.fn();
    on = vi.fn();
    off = vi.fn();
    getCamera() {
      return {
        animate: vi.fn(),
        animatedReset: vi.fn(),
        ratio: 1,
      };
    }
  },
}));

import { SigmaOperationalGraphAdapter } from '@/features/operational-graph/adapters/sigma-operational-graph-adapter';
import { defaultGraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';
import {
  getBenchmarkDataset,
  defaultGraphBenchmarkManifest,
} from '@/features/operational-graph/contracts/benchmark-manifest';
import { buildLodRenderHints } from '@/features/operational-graph/performance/lod-controller';

describe('graph renderer interaction performance', () => {
  it('syncs target graph within adapter budget', () => {
    const snapshot = buildTargetGraphSnapshot();
    const store = createGraphStore();
    store.loadSnapshot(snapshot);

    const container = document.createElement('div');
    document.body.appendChild(container);
    const adapter = new SigmaOperationalGraphAdapter(container);
    const filterSet = defaultGraphVisualState.filterSet as GraphFilterSet;
    const filtered = store.applyFilters(filterSet);
    const lodHints = buildLodRenderHints({
      visibleNodeIds: filtered.visibleNodeIds,
      visibleEdgeIds: filtered.visibleEdgeIds,
      highlightedEdgeIds: [],
      collapsedClusterIds: [],
    });

    const startedAt = performance.now();
    adapter.syncFromStore(store, filterSet, defaultGraphVisualState, {
      lodHints,
    });
    const elapsed = performance.now() - startedAt;
    const budget = getBenchmarkDataset(defaultGraphBenchmarkManifest, 'target').adapterSyncBudgetMs;

    expect(elapsed).toBeLessThan(budget);
    adapter.dispose();
    document.body.removeChild(container);
  });
});
