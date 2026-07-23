'use client';

import { useMemo } from 'react';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import { useLiveRun } from '@/features/live-run';
import { useRunGraph } from '@/features/shell/hooks/use-shell-queries';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface SelectedAsset {
  node: GraphNodeV1;
  /** True when the operator may see the asset's true security state (fog of war). */
  disclosed: boolean;
}

/**
 * Resolve the currently-selected graph asset from whichever projection is authoritative:
 * the live-run bootstrap snapshot in live mode, else the fetched run-graph snapshot. Returns
 * null when nothing (or a non-asset entity) is selected. Used to anchor operator direct
 * actions and the deep-dive drawer to a concrete asset without a dedicated backend lookup —
 * it degrades to graph-store data until the console asset-detail endpoint lands.
 */
export function useSelectedAsset(runId: string): SelectedAsset | null {
  const selectedEntityId = useWorkspaceUiStore((s) => s.workspace.selectedEntityId);
  const liveRun = useLiveRun();
  const graphQuery = useRunGraph(runId, { enabled: liveRun?.isLiveMode !== true });

  const snapshot = liveRun?.isLiveMode ? liveRun.bootstrapSnapshot : graphQuery.data?.snapshot;

  return useMemo(() => {
    if (!selectedEntityId || !snapshot) {
      return null;
    }
    const node = snapshot.nodes.find((candidate) => candidate.id === selectedEntityId);
    if (!node || node.entityType !== 'asset') {
      return null;
    }
    return { node, disclosed: node.disclosed !== false };
  }, [selectedEntityId, snapshot]);
}
