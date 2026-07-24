import { createGraphStore } from '@aegis/graph-domain';
import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';
import { describe, expect, it, vi } from 'vitest';

const captureSigmaSettings = vi.hoisted(() => vi.fn());

vi.mock('sigma', () => ({
  default: class MockSigma {
    constructor(_graph: unknown, _container: unknown, settings: unknown) {
      captureSigmaSettings(settings);
    }

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

  it('encodes asset type, risk, and selection as explicit renderer attributes', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const container = document.createElement('div');
    document.body.appendChild(container);
    const adapter = new SigmaOperationalGraphAdapter(container);

    adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      {
        ...defaultGraphVisualState,
        selection: {
          ...defaultGraphVisualState.selection,
          primaryNodeId: 'asset:svc-api-gateway',
        },
      },
    );

    const graph = adapter.getPresentationGraph();
    const selected = graph.getNodeAttributes('asset:svc-api-gateway');
    const device = graph.getNodeAttributes('asset:device-laptop-remote');
    const database = graph.getNodeAttributes('asset:db-customer-records');

    expect(selected.type).toBe('circle');
    expect(selected.assetType).toBe('service');
    expect(selected.shape).toBe('circle');
    expect(selected.forceLabel).toBe(true);
    expect(selected.highlighted).toBe(true);
    expect(selected.selected).toBe(true);
    expect(device.assetType).toBe('device');
    expect(device.shape).toBe('diamond');
    expect(device.riskBand).toBe('critical');
    expect(device.riskColor).toMatch(/^#/);
    expect(device.forceLabel).toBe(true);
    expect(database.assetType).toBe('database');
    expect(database.shape).toBe('square');
    expect(database.highlighted).toBe(true);

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

  it('fires the fog-of-war reveal when a node escalates between syncs', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const normalNode = snapshot.nodes.find((node) => node.status === 'normal');
    if (!normalNode) {
      throw new Error('fixture needs a normal-status node');
    }

    const container = document.createElement('div');
    document.body.appendChild(container);
    const adapter = new SigmaOperationalGraphAdapter(container);
    const filterSet =
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet;

    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    adapter.syncFromStore(store, filterSet, defaultGraphVisualState);
    expect(adapter.getLastRevealedNodeIds()).toEqual([]);

    const escalated = {
      ...snapshot,
      nodes: snapshot.nodes.map((node) =>
        node.id === normalNode.id ? { ...node, status: 'compromised' as const } : node,
      ),
    };
    const nextStore = createGraphStore();
    nextStore.loadSnapshot(escalated);
    adapter.syncFromStore(nextStore, filterSet, defaultGraphVisualState);
    expect(adapter.getLastRevealedNodeIds()).toEqual([normalNode.id]);

    // A third sync with no change must not re-fire the beat.
    adapter.syncFromStore(nextStore, filterSet, defaultGraphVisualState);
    expect(adapter.getLastRevealedNodeIds()).toEqual([]);

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

  it('keeps semantic labels and overlays visible while the fit camera settles', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const adapter = new SigmaOperationalGraphAdapter(container);

    adapter.mount();

    expect(captureSigmaSettings).toHaveBeenLastCalledWith(
      expect.objectContaining({ hideLabelsOnMove: false }),
    );
    adapter.dispose();
    document.body.removeChild(container);
  });
});
