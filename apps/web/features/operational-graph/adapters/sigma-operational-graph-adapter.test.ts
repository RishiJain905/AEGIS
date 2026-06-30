import { createGraphStore } from '@aegis/graph-domain';
import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';
import { describe, expect, it, vi } from 'vitest';

vi.mock('sigma', () => ({
  default: class MockSigma {
    kill = vi.fn();
    refresh = vi.fn();
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

import shellDataset from '@/fixtures/shell-dataset.json';

describe('SigmaOperationalGraphAdapter', () => {
  it('projects visible nodes from GraphStore without inventing entities', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);

    const store = createGraphStore();
    store.loadSnapshot(snapshot);

    const container = document.createElement('div');
    container.style.width = '400px';
    container.style.height = '400px';
    document.body.appendChild(container);

    const adapter = new SigmaOperationalGraphAdapter(container);
    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
    );

    expect(projection.nodeCount).toBeGreaterThan(1);
    expect(projection.edgeCount).toBeGreaterThan(0);
    expect(projection.visibleNodeIds).toContain('asset:svc-api-gateway');

    adapter.dispose();
    document.body.removeChild(container);
  });

  it('applies LOD edge reduction and collapsed cluster presentation nodes', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const container = document.createElement('div');
    document.body.appendChild(container);
    const adapter = new SigmaOperationalGraphAdapter(container);

    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      {
        ...defaultGraphVisualState,
        collapsedClusterIds: ['business-unit:retail'],
      },
      {
        lodHints: {
          tierId: 'dense',
          maxVisibleEdges: 2,
          labelMode: 'selected',
          clusterCollapseThreshold: 2,
          edgeOpacityFloor: 0.1,
          labelRenderedSizeThreshold: 20,
          labelDensity: 0.1,
          renderEdgeLabels: false,
          visibleEdgeIds: snapshot.edges.slice(0, 2).map((edge) => edge.id),
          collapsedClusterIds: ['business-unit:retail'],
        },
      },
    );

    expect(projection.edgeCount).toBeLessThanOrEqual(2);
    adapter.dispose();
    document.body.removeChild(container);
  });

  it('disposes sigma and clears graph on cleanup', () => {
    const container = document.createElement('div');
    container.style.width = '200px';
    container.style.height = '200px';
    document.body.appendChild(container);

    const adapter = new SigmaOperationalGraphAdapter(container);
    adapter.mount();
    adapter.dispose();

    expect(adapter.getPresentationGraph().order).toBe(0);
    document.body.removeChild(container);
  });
});
