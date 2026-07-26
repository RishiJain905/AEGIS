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
  PANEL_PREFERENCES_STORAGE_KEY,
  parsePanelPreferences,
  type PanelPreferences,
  type PanelRegion,
  type ThemePreference,
} from '@/features/shell/contracts/panel-preferences';

interface WorkspaceUiState {
  workspace: OperatorWorkspaceState;
  panelPreferences: PanelPreferences;
  activeRunId: string | null;
  mobileRailOpen: boolean;
  /**
   * Whether the operational graph's view-options panel is open. Mirrored out of the graph
   * view's local state so observers outside the canvas (the guided walkthrough) can tell the
   * panel is open without sniffing the DOM. Ephemeral — never persisted.
   */
  graphViewOptionsOpen: boolean;
  /**
   * Selection model — two selections, deliberately orthogonal, and they cannot disagree
   * because they name different kinds of thing:
   *
   * - `selectedEntityId` is the **graph pointer**. It only ever holds a graph node id
   *   (`asset:…` or a cluster), because assets and clusters are the only node kinds the
   *   graph snapshot contains. It answers "what am I looking at" and drives the entity
   *   inspector, the risk explanation, incident context and the asset command bar.
   * - `selectedIncidentId` is the **open case file**. It answers "what am I working" and
   *   drives the investigation record, BASTION proposals, the WARDEN decision and the
   *   approval gate in the run cockpit's right dock.
   *
   * So: clicking an asset moves the pointer and leaves the open case alone; clicking an
   * incident opens a case and leaves the pointer alone. Incidents are not graph nodes, so
   * "an incident selected on the graph" cannot arise — never put an incident id into
   * `selectedEntityId` (it used to happen, and only produced a pointer that matched no
   * node). Both are cleared together by `resetForRun` when the run changes.
   */
  setSelectedEntityId: (entityId: string | null) => void;
  setSelectedIncidentId: (incidentId: string | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setPresentationMode: (mode: PresentationMode) => void;
  setTimelineCursorSequence: (sequence: number | null) => void;
  setFocusRestorationToken: (token: string | null) => void;
  togglePanelCollapsed: (region: PanelRegion) => void;
  setPanelCollapsed: (region: PanelRegion, collapsed: boolean) => void;
  setTheme: (theme: ThemePreference) => void;
  setMobileRailOpen: (open: boolean) => void;
  setGraphViewOptionsOpen: (open: boolean) => void;
  resetForRun: (runId: string | null) => void;
}

export const useWorkspaceUiStore = create<WorkspaceUiState>()(
  persist(
    (set, get) => ({
      workspace: defaultOperatorWorkspaceState,
      panelPreferences: defaultPanelPreferences,
      activeRunId: null,
      mobileRailOpen: false,
      graphViewOptionsOpen: false,

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

      setTheme: (theme) => {
        set((state) => ({
          panelPreferences: { ...state.panelPreferences, theme },
        }));
      },

      setMobileRailOpen: (open) => {
        set({ mobileRailOpen: open });
      },

      setGraphViewOptionsOpen: (open) => {
        if (get().graphViewOptionsOpen === open) {
          return;
        }
        set({ graphViewOptionsOpen: open });
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
      name: PANEL_PREFERENCES_STORAGE_KEY,
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
