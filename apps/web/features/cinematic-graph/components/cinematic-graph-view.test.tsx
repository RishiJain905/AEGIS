import { useEffect } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';

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
