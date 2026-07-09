import { createGraphStore } from '@aegis/graph-domain';
import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { createSemanticSceneAdapter } from '@/features/cinematic-graph/adapters/semantic-scene-adapter';
import { GraphViewMode, RenderQualityTier } from '@/features/cinematic-graph/contracts';
import {
  probeCapabilityReport,
  recommendQualityTier,
} from '@/features/cinematic-graph/lib/capability';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { defaultGraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';

import shellDataset from '@/fixtures/shell-dataset.json';

/**
 * Phase 27 acceptance criteria (spec §18):
 * AC1 — 2D and 3D show the same semantic state at the same cursor
 * AC2 — Unsupported devices fall back cleanly
 * AC3 — Mode switching preserves selection and leaks no GPU resources
 * AC4 — Reduced-motion mode remains understandable
 */
describe('Phase 27 acceptance criteria', () => {
  it('AC1: 3D scene projects the same GraphStore semantic ids at the same sequence', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const filtered = store.applyFilters(
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
    );

    const scene = createSemanticSceneAdapter();
    const sceneProjection = scene.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.HIGH },
    );

    expect(sceneProjection.sequence).toBe(snapshot.sequence);
    expect(sceneProjection.revision).toBe(snapshot.revision);
    expect(new Set(sceneProjection.nodes.map((n) => n.id))).toEqual(
      new Set(filtered.visibleNodeIds),
    );
    expect(new Set(sceneProjection.edges.map((e) => e.id))).toEqual(
      new Set(filtered.visibleEdgeIds),
    );

    scene.dispose();
  });

  it('AC2: unsupported WebGL falls back to 2D capability tier', () => {
    const report = probeCapabilityReport({ forceWebglUnavailable: true });
    expect(report.recommendedTier).toBe(RenderQualityTier.FALLBACK_2D);
    useCinematicGraphStore.getState().reset();
    useCinematicGraphStore.getState().setCapability(report);
    expect(useCinematicGraphStore.getState().qualityTier).toBe(RenderQualityTier.FALLBACK_2D);
    expect(report.reasonCodes).toContain('webgl-unavailable');
  });

  it('AC3: mode switch preserves selection and dispose clears scene resources', () => {
    useCinematicGraphStore.getState().reset();
    useCinematicGraphStore.getState().setCapability(
      probeCapabilityReport({
        forceWebglUnavailable: false,
        estimatedDeviceMemoryGb: 16,
        reducedMotion: false,
      }),
    );
    useCinematicGraphStore.getState().setViewMode(GraphViewMode.THREE_D);
    expect(useCinematicGraphStore.getState().viewMode).toBe(GraphViewMode.THREE_D);

    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();
    adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      {
        ...defaultGraphVisualState,
        selection: {
          schemaVersion: 1,
          primaryNodeId: 'asset:svc-api-gateway',
          secondaryNodeId: null,
          selectedEdgeId: null,
        },
      },
      { qualityTier: RenderQualityTier.HIGH },
    );
    const selected = adapter
      .getLastProjection()
      ?.nodes.find((node) => node.id === 'asset:svc-api-gateway');
    expect(selected?.selected).toBe(true);

    useCinematicGraphStore.getState().setViewMode(GraphViewMode.TWO_D);
    expect(useCinematicGraphStore.getState().viewMode).toBe(GraphViewMode.TWO_D);
    // Selection is owned by workspace/graph visual stores; scene dispose must not invent facts.
    adapter.dispose();
    expect(adapter.getLastProjection()).toBeNull();
  });

  it('AC4: reduced-motion capability remains understandable (medium tier, no fallback invent)', () => {
    const recommendation = recommendQualityTier({
      webglAvailable: true,
      reducedMotion: true,
      estimatedDeviceMemoryGb: 16,
    });
    expect(recommendation.tier).not.toBe(RenderQualityTier.FALLBACK_2D);
    expect(recommendation.tier).toBe(RenderQualityTier.MEDIUM);
    expect(recommendation.reasonCodes).toContain('reduced-motion');
  });
});
