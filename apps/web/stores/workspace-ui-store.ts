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

/**
 * The run the operator is working, remembered across surfaces and reloads.
 *
 * Distinct from `activeRunId`, which is the *workspace reset key*: mounting a shell
 * without a run calls `resetForRun(null)` and clears it, so it goes null the moment the
 * operator opens Incidents or Reports. The rail's run-scoped destinations need the
 * opposite lifetime — they have to keep pointing at the run you came from — so they read
 * this instead.
 *
 * `userId` is stored with it because it is persisted: without the check, signing in as a
 * different identity would inherit the previous operator's run id and navigate straight
 * into a 403 workspace.
 */
export interface RunContext {
  runId: string;
  userId: string;
}

interface WorkspaceUiState {
  workspace: OperatorWorkspaceState;
  panelPreferences: PanelPreferences;
  activeRunId: string | null;
  runContext: RunContext | null;
  mobileRailOpen: boolean;
  /**
   * Whether the operational graph's view-options panel is open. Mirrored out of the graph
   * view's local state so observers outside the canvas (the guided walkthrough) can tell the
   * panel is open without sniffing the DOM. Ephemeral — never persisted.
   */
  graphViewOptionsOpen: boolean;
  /**
   * Whether the operator has opened an alert's Explanation disclosure. Mirrors
   * `graphViewOptionsOpen`'s pattern: the alerts panel calls `setAlertExplanationOpened(true)`
   * when a card's Explanation section opens, so the guided walkthrough (BUG-005) can require
   * the real disclosure interaction rather than merely an alert existing. Ephemeral — never
   * persisted, and never reset to `false` on collapse — the objective only cares that it
   * happened once.
   *
   * NOTE for the alerts-panel owner: this flag exists so the tutorial's "read the
   * explanation" objective (see `features/tutorial/tutorial-content.ts`, beat
   * `alert-anatomy`) can complete correctly. Please wire `setAlertExplanationOpened(true)`
   * into wherever the alert card's Explanation disclosure toggles open.
   */
  alertExplanationOpened: boolean;
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
  setAlertExplanationOpened: (open: boolean) => void;
  resetForRun: (runId: string | null) => void;
  /** Remember the run the operator entered. Never cleared by `resetForRun(null)`. */
  rememberRunContext: (context: RunContext) => void;
  /** Forget it — on sign-out, or when the stored identity is not the current one. */
  clearRunContext: () => void;
}

function parseRunContext(value: unknown): RunContext | null {
  if (typeof value !== 'object' || value === null) {
    return null;
  }
  const candidate = value as Partial<RunContext>;
  if (typeof candidate.runId !== 'string' || typeof candidate.userId !== 'string') {
    return null;
  }
  return { runId: candidate.runId, userId: candidate.userId };
}

export const useWorkspaceUiStore = create<WorkspaceUiState>()(
  persist(
    (set, get) => ({
      workspace: defaultOperatorWorkspaceState,
      panelPreferences: defaultPanelPreferences,
      activeRunId: null,
      runContext: null,
      mobileRailOpen: false,
      graphViewOptionsOpen: false,
      alertExplanationOpened: false,

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

      setAlertExplanationOpened: (open) => {
        if (get().alertExplanationOpened === open) {
          return;
        }
        set({ alertExplanationOpened: open });
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

      rememberRunContext: (context) => {
        const current = get().runContext;
        if (current?.runId === context.runId && current.userId === context.userId) {
          return;
        }
        set({ runContext: context });
      },

      clearRunContext: () => {
        if (get().runContext === null) {
          return;
        }
        set({ runContext: null });
      },
    }),
    {
      name: PANEL_PREFERENCES_STORAGE_KEY,
      partialize: (state) => ({
        panelPreferences: state.panelPreferences,
        runContext: state.runContext,
      }),
      merge: (persisted, current) => {
        const persistedState = persisted as Partial<WorkspaceUiState> | undefined;
        return {
          ...current,
          panelPreferences: parsePanelPreferences(persistedState?.panelPreferences),
          runContext: parseRunContext(persistedState?.runContext),
        };
      },
    },
  ),
);
