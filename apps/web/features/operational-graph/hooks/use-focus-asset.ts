'use client';

import { useCallback } from 'react';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

/**
 * Point the operator at an asset from anywhere outside the canvas.
 *
 * Panels that name an asset — alerts, the ops feed — should be able to hand the operator
 * straight to the node instead of printing a raw `asset:` id and leaving them to find it.
 * Two stores have to move together for that: the workspace pointer (drives the inspector,
 * risk explanation and command bar) and the graph's visual selection (drives the highlight
 * and, via the view's focus effect, the camera). Doing both in one place keeps the two from
 * drifting apart, which is how a selected asset ends up highlighted but not inspected.
 */
export function useFocusAsset(): (assetId: string) => void {
  const setSelectedEntityId = useWorkspaceUiStore((state) => state.setSelectedEntityId);
  const setSelection = useGraphVisualStore((state) => state.setSelection);

  return useCallback(
    (assetId: string) => {
      setSelectedEntityId(assetId);
      setSelection(assetId, null);
    },
    [setSelectedEntityId, setSelection],
  );
}
