import { createGraphStore } from '@aegis/graph-domain';
import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { createSemanticSceneAdapter } from '@/features/cinematic-graph/adapters/semantic-scene-adapter';
import { RenderQualityTier } from '@/features/cinematic-graph/contracts';
import { defaultGraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';

import shellDataset from '@/fixtures/shell-dataset.json';

const SYNC_BUDGET_MS = 250;

describe('cinematic renderer performance', () => {
  it('syncs Operation Silent Relay fixture within budget and disposes cleanly', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();

    const started = performance.now();
    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.HIGH },
    );
    const elapsed = performance.now() - started;

    expect(projection.nodeCount).toBeGreaterThan(0);
    expect(elapsed).toBeLessThan(SYNC_BUDGET_MS);

    adapter.dispose();
    expect(adapter.getLastProjection()).toBeNull();
  });

  it('repeated sync+dispose cycles do not retain last projection', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);

    for (let i = 0; i < 5; i += 1) {
      const adapter = createSemanticSceneAdapter();
      adapter.syncFromStore(
        store,
        defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
        defaultGraphVisualState,
        { qualityTier: RenderQualityTier.MEDIUM },
      );
      expect(adapter.getLastProjection()).not.toBeNull();
      adapter.dispose();
      expect(adapter.getLastProjection()).toBeNull();
    }
  });
});
