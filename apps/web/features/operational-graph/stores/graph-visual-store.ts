import { create } from 'zustand';

import {
  defaultGraphVisualState,
  GraphHighlightMode,
  type GraphVisualState,
} from '@/features/operational-graph/contracts/graph-visual-state';
import type { GraphFilterSet } from '@aegis/graph-domain';

interface GraphVisualStore {
  visualState: GraphVisualState;
  setSearchQuery: (query: string) => void;
  setFilterSet: (filterSet: GraphFilterSet) => void;
  setHoveredNodeId: (nodeId: string | null) => void;
  setSelection: (primaryNodeId: string | null, secondaryNodeId?: string | null) => void;
  setHighlight: (
    mode: GraphVisualState['highlightMode'],
    nodeIds: string[],
    edgeIds: string[],
    isolationActive?: boolean,
  ) => void;
  clearHighlight: () => void;
  setPathModeActive: (active: boolean) => void;
  toggleOverlay: (key: keyof GraphVisualState['overlayToggles']) => void;
  setNodePositions: (positions: Record<string, { x: number; y: number }>) => void;
  mergeNodePositions: (positions: Record<string, { x: number; y: number }>) => void;
  resetVisualState: () => void;
}

export const useGraphVisualStore = create<GraphVisualStore>()((set) => ({
  visualState: defaultGraphVisualState,

  setSearchQuery: (query) => {
    set((state) => ({
      visualState: { ...state.visualState, searchQuery: query },
    }));
  },

  setFilterSet: (filterSet) => {
    set((state) => ({
      visualState: { ...state.visualState, filterSet },
    }));
  },

  setHoveredNodeId: (nodeId) => {
    set((state) => ({
      visualState: { ...state.visualState, hoveredNodeId: nodeId },
    }));
  },

  setSelection: (primaryNodeId, secondaryNodeId = null) => {
    set((state) => ({
      visualState: {
        ...state.visualState,
        selection: {
          ...state.visualState.selection,
          primaryNodeId,
          secondaryNodeId: secondaryNodeId ?? state.visualState.selection.secondaryNodeId,
        },
      },
    }));
  },

  setHighlight: (mode, nodeIds, edgeIds, isolationActive = false) => {
    set((state) => ({
      visualState: {
        ...state.visualState,
        highlightMode: mode,
        highlightedNodeIds: nodeIds,
        highlightedEdgeIds: edgeIds,
        isolationActive,
      },
    }));
  },

  clearHighlight: () => {
    set((state) => ({
      visualState: {
        ...state.visualState,
        highlightMode: GraphHighlightMode.NONE,
        highlightedNodeIds: [],
        highlightedEdgeIds: [],
        isolationActive: false,
      },
    }));
  },

  setPathModeActive: (active) => {
    set((state) => ({
      visualState: {
        ...state.visualState,
        pathModeActive: active,
        selection: active
          ? state.visualState.selection
          : {
              ...state.visualState.selection,
              secondaryNodeId: null,
            },
      },
    }));
  },

  toggleOverlay: (key) => {
    set((state) => ({
      visualState: {
        ...state.visualState,
        overlayToggles: {
          ...state.visualState.overlayToggles,
          [key]: !state.visualState.overlayToggles[key],
        },
      },
    }));
  },

  setNodePositions: (positions) => {
    set((state) => ({
      visualState: { ...state.visualState, nodePositions: positions },
    }));
  },

  mergeNodePositions: (positions) => {
    set((state) => ({
      visualState: {
        ...state.visualState,
        nodePositions: { ...state.visualState.nodePositions, ...positions },
      },
    }));
  },

  resetVisualState: () => {
    set({ visualState: defaultGraphVisualState });
  },
}));

export function getGraphVisualState(): GraphVisualState {
  return get().visualState;
}

function get(): GraphVisualStore {
  return useGraphVisualStore.getState();
}
