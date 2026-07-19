import type { GraphStore } from '@aegis/graph-domain';

import { GraphHighlightMode, type GraphVisualState } from '../contracts/graph-visual-state';

export interface HighlightSelectionResult {
  highlightedNodeIds: string[];
  highlightedEdgeIds: string[];
}

/**
 * Pure GraphStore highlight resolution shared by the Sigma (2D) adapter and
 * the cinematic (3D) view, so investigation-focus actions behave identically
 * in both renderers.
 */
export function computeHighlight(
  store: GraphStore,
  visualState: GraphVisualState,
): HighlightSelectionResult {
  const { highlightMode, selection } = visualState;

  if (highlightMode === GraphHighlightMode.NONE || !selection.primaryNodeId) {
    return { highlightedNodeIds: [], highlightedEdgeIds: [] };
  }

  switch (highlightMode) {
    case GraphHighlightMode.NEIGHBORHOOD: {
      const result = store.getNeighborhood(selection.primaryNodeId, {
        hops: 1,
      });
      return {
        highlightedNodeIds: result.nodeIds,
        highlightedEdgeIds: result.edgeIds,
      };
    }
    case GraphHighlightMode.PATH: {
      if (!selection.secondaryNodeId) {
        return {
          highlightedNodeIds: [selection.primaryNodeId],
          highlightedEdgeIds: [],
        };
      }
      const pathResult = store.queryPaths({
        schemaVersion: 1,
        runId: store.getRunId() ?? '',
        sourceId: selection.primaryNodeId,
        targetId: selection.secondaryNodeId,
        maxHops: 8,
        relationshipTypes: [],
        directedOnly: false,
      });
      const path = pathResult.paths[0] ?? [];
      const edgeIds: string[] = [];
      const snapshot = store.exportSnapshot();
      for (let i = 0; i < path.length - 1; i += 1) {
        for (const edge of snapshot.edges) {
          if (
            (edge.source === path[i] && edge.target === path[i + 1]) ||
            (edge.source === path[i + 1] && edge.target === path[i])
          ) {
            edgeIds.push(edge.id);
          }
        }
      }
      return { highlightedNodeIds: path, highlightedEdgeIds: edgeIds };
    }
    case GraphHighlightMode.INCIDENT: {
      const result = store.getIncidentSubgraph([selection.primaryNodeId], {
        hops: 2,
      });
      return {
        highlightedNodeIds: result.nodeIds,
        highlightedEdgeIds: result.edgeIds,
      };
    }
    case GraphHighlightMode.DEPENDENCIES: {
      const deps = store.getDependencies(selection.primaryNodeId, 3);
      return {
        highlightedNodeIds: [selection.primaryNodeId, ...deps],
        highlightedEdgeIds: [],
      };
    }
    default: {
      const _exhaustive: never = highlightMode;
      throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
    }
  }
}
