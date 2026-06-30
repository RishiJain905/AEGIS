import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';

import {
  defaultOperatorWorkspaceState,
  type OperatorWorkspaceState,
  type PresentationMode,
} from '@/features/shell/contracts/operator-workspace-state';
import {
  defaultPanelPreferences,
  parsePanelPreferences,
  type PanelPreferences,
  type PanelRegion,
} from '@/features/shell/contracts/panel-preferences';

interface WorkspaceUiState {
  workspace: OperatorWorkspaceState;
  panelPreferences: PanelPreferences;
  activeRunId: string | null;
  mobileRailOpen: boolean;
  setSelectedEntityId: (entityId: string | null) => void;
  setSelectedIncidentId: (incidentId: string | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setPresentationMode: (mode: PresentationMode) => void;
  setTimelineCursorSequence: (sequence: number | null) => void;
  setFocusRestorationToken: (token: string | null) => void;
  togglePanelCollapsed: (region: PanelRegion) => void;
  setPanelCollapsed: (region: PanelRegion, collapsed: boolean) => void;
  setMobileRailOpen: (open: boolean) => void;
  resetForRun: (runId: string | null) => void;
}

export const useWorkspaceUiStore = create<WorkspaceUiState>()(
  persist(
    (set, get) => ({
      workspace: defaultOperatorWorkspaceState,
      panelPreferences: defaultPanelPreferences,
      activeRunId: null,
      mobileRailOpen: false,

      setSelectedEntityId: (entityId) => {
        set((state) => ({
          workspace: { ...state.workspace, selectedEntityId: entityId },
        }));
      },

      setSelectedIncidentId: (incidentId) => {
        set((state) => ({
          workspace: { ...state.workspace, selectedIncidentId: incidentId },
        }));
      },

      setCommandPaletteOpen: (open) => {
        set((state) => ({
          workspace: { ...state.workspace, commandPaletteOpen: open },
        }));
      },

      setPresentationMode: (mode) => {
        set((state) => ({
          workspace: { ...state.workspace, presentationMode: mode },
        }));
      },

      setTimelineCursorSequence: (sequence) => {
        set((state) => ({
          workspace: { ...state.workspace, timelineCursorSequence: sequence },
        }));
      },

      setFocusRestorationToken: (token) => {
        set((state) => ({
          workspace: { ...state.workspace, focusRestorationToken: token },
        }));
      },

      togglePanelCollapsed: (region) => {
        const current = get().panelPreferences.regions[region];
        if (!current) {
          return;
        }
        set((state) => ({
          panelPreferences: {
            ...state.panelPreferences,
            regions: {
              ...state.panelPreferences.regions,
              [region]: { ...current, collapsed: !current.collapsed },
            },
          },
        }));
      },

      setPanelCollapsed: (region, collapsed) => {
        const current = get().panelPreferences.regions[region];
        if (!current) {
          return;
        }
        set((state) => ({
          panelPreferences: {
            ...state.panelPreferences,
            regions: {
              ...state.panelPreferences.regions,
              [region]: { ...current, collapsed },
            },
          },
        }));
      },

      setMobileRailOpen: (open) => {
        set({ mobileRailOpen: open });
      },

      resetForRun: (runId) => {
        if (get().activeRunId === runId) {
          return;
        }
        useGraphVisualStore.getState().resetVisualState();
        set({
          activeRunId: runId,
          workspace: {
            ...defaultOperatorWorkspaceState,
            presentationMode: runId ? 'live' : defaultOperatorWorkspaceState.presentationMode,
          },
        });
      },
    }),
    {
      name: 'aegis-panel-preferences-v1',
      partialize: (state) => ({ panelPreferences: state.panelPreferences }),
      merge: (persisted, current) => {
        const persistedState = persisted as Partial<WorkspaceUiState> | undefined;
        return {
          ...current,
          panelPreferences: parsePanelPreferences(persistedState?.panelPreferences),
        };
      },
    },
  ),
);
