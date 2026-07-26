import { useEffect } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';
import { createGraphStore } from '@aegis/graph-domain';

import shellDataset from '@/fixtures/shell-dataset.json';
import { SemanticSceneAdapterImpl } from '@/features/cinematic-graph/adapters/semantic-scene-adapter';
import { CinematicGraphView } from '@/features/cinematic-graph/components/cinematic-graph-view';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';

vi.mock('next/dynamic', () => ({
  default: () =>
    function MockCinematicSceneCanvas(props: {
      nodes: unknown[];
      camera: unknown;
      onReady?: () => void;
    }) {
      useEffect(() => {
        props.onReady?.();
      }, [props.onReady]);

      return (
        <div
          data-testid="mock-cinematic-scene-canvas"
          data-node-count={String(props.nodes.length)}
          data-camera={JSON.stringify(props.camera)}
        />
      );
    },
}));

vi.mock('@aegis/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@aegis/ui')>();
  return {
    ...actual,
    useReducedMotion: () => false,
  };
});

vi.mock('@/features/cinematic-graph/lib/capability', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/cinematic-graph/lib/capability')>();
  return {
    ...actual,
    probeCapabilityReport: () => ({
      schemaVersion: 1 as const,
      webglAvailable: true,
      webgl2Available: true,
      maxTextureSize: 16_384,
      devicePixelRatioCap: 1.5,
      reducedMotion: false,
      recommendedTier: 'high' as const,
      reasonCodes: [],
      estimatedDeviceMemoryGb: 16,
    }),
  };
});

describe('CinematicGraphView synchronization', () => {
  beforeEach(() => {
    cleanup();
    vi.restoreAllMocks();
    useCinematicGraphStore.getState().reset();
    useGraphVisualStore.getState().resetVisualState();
  });

  it('does not resynchronize indefinitely when optional marker ids are omitted', async () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);
    const sync = vi.spyOn(SemanticSceneAdapterImpl.prototype, 'syncFromStore');

    render(<CinematicGraphView snapshot={snapshot} runId={snapshot.runId} />);

    await screen.findByTestId('cinematic-graph-meta');
    await waitFor(() => {
      expect(sync.mock.calls.length).toBeLessThanOrEqual(3);
    });
    expect(screen.queryByTestId('cinematic-graph-error')).not.toBeInTheDocument();
  });

  it('re-derives the scene from the shared store when the graph revision advances', async () => {
    // The theater is a read-only projection of the live GraphStore. A delta applied to
    // that store is announced only by a bumped graphRevision, so the scene has to
    // re-derive on that prop — once per graph change, not once per event envelope.
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const sync = vi.spyOn(SemanticSceneAdapterImpl.prototype, 'syncFromStore');

    const view = render(
      <CinematicGraphView
        snapshot={snapshot}
        runId={snapshot.runId}
        graphStore={store}
        graphRevision={snapshot.revision}
      />,
    );
    await screen.findByTestId('cinematic-graph-meta');
    await waitFor(() => {
      expect(sync).toHaveBeenCalled();
    });

    const target = snapshot.nodes[0];
    if (!target) {
      throw new Error('shell dataset snapshot must contain at least one node');
    }
    store.applyDelta({
      schemaVersion: 1,
      runId: snapshot.runId,
      sequence: snapshot.sequence + 1,
      revision: snapshot.revision + 1,
      operation: 'upsert_node',
      node: { ...target, status: 'compromised', revision: target.revision + 1 },
    });

    const before = sync.mock.calls.length;
    view.rerender(
      <CinematicGraphView
        snapshot={snapshot}
        runId={snapshot.runId}
        graphStore={store}
        graphRevision={snapshot.revision + 1}
      />,
    );

    await waitFor(() => {
      expect(sync.mock.calls.length).toBeGreaterThan(before);
    });
    // The re-derived projection carries the store's advanced revision, and the
    // status-derived incident scope picked up the newly compromised asset rather
    // than staying frozen on the mount-time bootstrap snapshot.
    const latest = sync.mock.results.at(-1);
    expect(latest?.type).toBe('return');
    expect((latest?.value as { revision: number }).revision).toBe(snapshot.revision + 1);
    const incidentIds = sync.mock.calls.at(-1)?.[3]?.incidentNodeIds as Set<string> | undefined;
    expect(incidentIds?.has(target.id)).toBe(true);
  });

  it('shows the live run event sequence rather than the graph projection sequence', async () => {
    // A live run streams hundreds of events that never mutate the graph, so the
    // projection sequence can sit at 0 all run. Reporting that as "sequence" read as
    // a dead theater; the operator's sequence is the run's applied event sequence.
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);

    render(<CinematicGraphView snapshot={snapshot} runId={snapshot.runId} liveSequence={481} />);

    const meta = await screen.findByTestId('cinematic-graph-meta');
    expect(meta.textContent).toContain('event 481');
    expect(meta.textContent).toContain(`graph revision ${String(snapshot.revision)}`);
  });

  it('gives the WebGL camera a bounded viewport aspect ratio', async () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);

    render(<CinematicGraphView snapshot={snapshot} runId={snapshot.runId} />);

    const frame = await screen.findByTestId('cinematic-canvas-frame');
    expect(frame.className).toContain('h-[clamp(28rem,62vh,46rem)]');
    expect(screen.getByTestId('cinematic-graph-view').className).not.toContain('h-full');
  });

  it('reapplies reset framing when the first populated projection reaches the canvas', async () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);
    const sync = vi.spyOn(SemanticSceneAdapterImpl.prototype, 'syncFromStore');
    const resetCamera = vi.spyOn(SemanticSceneAdapterImpl.prototype, 'resetCamera');

    render(<CinematicGraphView snapshot={snapshot} runId={snapshot.runId} />);

    const canvas = await screen.findByTestId('mock-cinematic-scene-canvas');
    await waitFor(() => {
      expect(canvas).toHaveAttribute('data-node-count', '38');
    });
    expect(
      sync.mock.results.some((result) => result.type === 'return' && result.value.nodeCount === 0),
    ).toBe(true);
    await waitFor(() => {
      expect(resetCamera).toHaveBeenCalledTimes(1);
    });
    expect(JSON.parse(canvas.getAttribute('data-camera') ?? 'null')).toEqual(
      resetCamera.mock.results[0]?.value,
    );
  });
});
