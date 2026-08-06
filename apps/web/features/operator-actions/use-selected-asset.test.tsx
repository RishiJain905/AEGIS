import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { useRunGraph, useLiveRun, useWorkspaceUiStore } = vi.hoisted(() => ({
  useRunGraph: vi.fn(),
  useLiveRun: vi.fn(),
  useWorkspaceUiStore: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({ useRunGraph }));
vi.mock('@/features/live-run', () => ({ useLiveRun }));
vi.mock('@/stores/workspace-ui-store', () => ({ useWorkspaceUiStore }));

import { useSelectedAsset } from './use-selected-asset';

const ASSET = 'asset:svc-identity-broker';

function snapshot(status: string, appliedControls: string[] = []): GraphSnapshotV1 {
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
        label: 'Identity Broker',
        riskScore: 0.4,
        criticality: 0.9,
        status,
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

describe('useSelectedAsset', () => {
  it('reads the REST snapshot when there is no live run', () => {
    useWorkspaceUiStore.mockReturnValue(ASSET);
    useLiveRun.mockReturnValue(null);
    useRunGraph.mockReturnValue({
      data: { snapshot: snapshot('suspicious') },
    });

    const { result } = renderHook(() => useSelectedAsset('run_x'));

    expect(result.current?.node.status).toBe('suspicious');
    expect(useRunGraph).toHaveBeenCalledWith('run_x', { enabled: true });
  });

  it('reads the live graph store instead of the frozen bootstrap snapshot, and re-resolves on a delta', () => {
    // The bug this exists to stop: the command bar resolved the selection from the
    // bootstrap snapshot, which only moves on bootstrap/resync. An executed containment
    // landed in the live store — the inspector showed `contained`/`Isolated` — while the
    // bar kept narrating the pre-action `normal` until the next resync.
    useWorkspaceUiStore.mockReturnValue(ASSET);
    const exportSnapshot = vi.fn().mockReturnValue(snapshot('contained', ['isolated']));
    useLiveRun.mockReturnValue({
      isLiveMode: true,
      bootstrapSnapshot: snapshot('normal'),
      graphStore: { exportSnapshot },
      graphRevision: 7,
    });
    useRunGraph.mockReturnValue({
      data: { snapshot: snapshot('normal') },
    });

    const { result, rerender } = renderHook(() => useSelectedAsset('run_x'));

    expect(result.current?.node.status).toBe('contained');
    expect(result.current?.node.appliedControls).toEqual(['isolated']);
    // The fetch is switched off in live mode.
    expect(useRunGraph).toHaveBeenCalledWith('run_x', { enabled: false });

    exportSnapshot.mockReturnValue(snapshot('contained', ['isolated', 'observed']));
    rerender();
    // Same revision, same export: a mutable store handed back by reference would otherwise
    // have to be re-read on every render.
    expect(result.current?.node.appliedControls).toEqual(['isolated']);

    useLiveRun.mockReturnValue({
      isLiveMode: true,
      bootstrapSnapshot: snapshot('normal'),
      graphStore: { exportSnapshot },
      graphRevision: 8,
    });
    rerender();
    expect(result.current?.node.appliedControls).toEqual(['isolated', 'observed']);
  });

  it('falls back to the fetch while a live run is still bootstrapping', () => {
    useWorkspaceUiStore.mockReturnValue(ASSET);
    useLiveRun.mockReturnValue({
      isLiveMode: true,
      bootstrapSnapshot: null,
      graphStore: { exportSnapshot: vi.fn() },
      graphRevision: 0,
    });
    useRunGraph.mockReturnValue({
      data: { snapshot: snapshot('compromised') },
    });

    const { result } = renderHook(() => useSelectedAsset('run_x'));

    expect(result.current?.node.status).toBe('compromised');
  });

  it('returns null when nothing is selected or the selection is not an asset', () => {
    useWorkspaceUiStore.mockReturnValue(null);
    useLiveRun.mockReturnValue(null);
    useRunGraph.mockReturnValue({ data: { snapshot: snapshot('normal') } });

    const { result } = renderHook(() => useSelectedAsset('run_x'));
    expect(result.current).toBeNull();
  });
});
