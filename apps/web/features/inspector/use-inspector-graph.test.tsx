import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { useRunGraph, useLiveRun } = vi.hoisted(() => ({
  useRunGraph: vi.fn(),
  useLiveRun: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({ useRunGraph }));
vi.mock('@/features/live-run', () => ({ useLiveRun }));

import { useInspectorGraph } from './use-inspector-graph';

const ASSET = 'asset:svc-comms-gateway';

function snapshot(appliedControls: string[]): GraphSnapshotV1 {
  return {
    schemaVersion: 1,
    runId: 'run_x',
    revision: 1,
    sequence: 1,
    capturedAt: '2026-01-01T00:00:00.000Z',
    nodes: [
      {
        schemaVersion: 1,
        id: ASSET,
        entityType: 'asset',
        assetType: 'service',
        label: 'Communications Gateway',
        riskScore: 0.4,
        criticality: 0.8,
        status: 'normal',
        revision: 1,
        appliedControls,
      },
    ],
    edges: [],
  } as unknown as GraphSnapshotV1;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('useInspectorGraph', () => {
  it('reads the REST snapshot when there is no live run', () => {
    useLiveRun.mockReturnValue(null);
    useRunGraph.mockReturnValue({
      isPending: false,
      isError: false,
      data: { snapshot: snapshot([]) },
      refetch: vi.fn(),
    });

    const { result } = renderHook(() => useInspectorGraph('run_x'));

    expect(result.current.snapshot?.nodes[0]?.appliedControls).toEqual([]);
    expect(useRunGraph).toHaveBeenCalledWith('run_x', { enabled: true });
  });

  it('reads the live graph store instead of the frozen fetch, and re-exports on a delta', () => {
    // The bug this exists to stop: the REST snapshot is fetched once and never invalidated,
    // so an executed containment landed in the store and the inspector kept rendering the
    // pre-action estate — an isolated asset reading "normal" with no control badge.
    const exportSnapshot = vi.fn().mockReturnValue(snapshot(['isolated']));
    useLiveRun.mockReturnValue({
      isLiveMode: true,
      bootstrapSnapshot: snapshot([]),
      graphStore: { exportSnapshot },
      graphRevision: 7,
    });
    useRunGraph.mockReturnValue({
      isPending: true,
      isError: false,
      data: { snapshot: snapshot([]) },
      refetch: vi.fn(),
    });

    const { result, rerender } = renderHook(() => useInspectorGraph('run_x'));

    expect(result.current.snapshot?.nodes[0]?.appliedControls).toEqual(['isolated']);
    // The fetch is switched off in live mode, and its pending state must not blank the panel.
    expect(useRunGraph).toHaveBeenCalledWith('run_x', { enabled: false });
    expect(result.current.isPending).toBe(false);

    exportSnapshot.mockReturnValue(snapshot(['isolated', 'observed']));
    rerender();
    // Same revision, same export: a mutable store handed back by reference would otherwise
    // have to be re-read on every render.
    expect(result.current.snapshot?.nodes[0]?.appliedControls).toEqual(['isolated']);

    useLiveRun.mockReturnValue({
      isLiveMode: true,
      bootstrapSnapshot: snapshot([]),
      graphStore: { exportSnapshot },
      graphRevision: 8,
    });
    rerender();
    expect(result.current.snapshot?.nodes[0]?.appliedControls).toEqual(['isolated', 'observed']);
  });

  it('falls back to the fetch while a live run is still bootstrapping', () => {
    useLiveRun.mockReturnValue({
      isLiveMode: true,
      bootstrapSnapshot: null,
      graphStore: { exportSnapshot: vi.fn() },
      graphRevision: 0,
    });
    useRunGraph.mockReturnValue({
      isPending: false,
      isError: false,
      data: { snapshot: snapshot(['observed']) },
      refetch: vi.fn(),
    });

    const { result } = renderHook(() => useInspectorGraph('run_x'));

    expect(result.current.snapshot?.nodes[0]?.appliedControls).toEqual(['observed']);
  });
});
