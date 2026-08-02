import { create } from 'zustand';

/**
 * Ephemeral chrome state for the one-stage cockpit: which furniture is currently
 * summoned over the stage. Never persisted — a reload lands the operator back in the
 * default reading of the room (stage + console + ambient signals), which is the point
 * of an attention-driven layout.
 *
 * The signals stack has three-valued state on purpose. `signalsPreference` records only
 * an explicit operator choice; while it is `null` the stack resolves automatically —
 * expanded when alerts exist, capsule when the floor is quiet — so the first alert of a
 * run opens the stack without the operator having to know it exists.
 */
export type SignalsPreference = 'expanded' | 'capsule';

/** One keystroke routed from the console into the copilot composer. */
export interface CopilotSeed {
  text: string;
  /** Monotonic token so the composer applies each seed exactly once. */
  token: number;
}

interface CockpitUiState {
  signalsPreference: SignalsPreference | null;
  /** Signals expanded as a popover OVER an open right sheet (the collision rule). */
  signalsOverlayOpen: boolean;
  inspectorSheetOpen: boolean;
  copilotSheetOpen: boolean;
  chronicleOpen: boolean;
  copilotSeed: CopilotSeed | null;
  setSignalsPreference: (preference: SignalsPreference | null) => void;
  setSignalsOverlayOpen: (open: boolean) => void;
  setInspectorSheetOpen: (open: boolean) => void;
  setCopilotSheetOpen: (open: boolean) => void;
  setChronicleOpen: (open: boolean) => void;
  /**
   * Route a keystroke typed on the console into the copilot composer: opens the copilot
   * sheet and hands the composer the character, making the console literally a command
   * line to the agents.
   */
  seedCopilotComposer: (text: string) => void;
  /** Back to the default reading of the room. Called when the run changes. */
  resetCockpitUi: () => void;
}

const DEFAULTS = {
  signalsPreference: null,
  signalsOverlayOpen: false,
  inspectorSheetOpen: false,
  copilotSheetOpen: false,
  chronicleOpen: false,
  copilotSeed: null,
} as const;

export const useCockpitUiStore = create<CockpitUiState>()((set, get) => ({
  ...DEFAULTS,

  setSignalsPreference: (preference) => {
    set({ signalsPreference: preference });
  },

  setSignalsOverlayOpen: (open) => {
    set({ signalsOverlayOpen: open });
  },

  setInspectorSheetOpen: (open) => {
    // Closing the sheet also closes anything the sheet owned.
    set(
      open
        ? { inspectorSheetOpen: true }
        : { inspectorSheetOpen: false, signalsOverlayOpen: false },
    );
  },

  setCopilotSheetOpen: (open) => {
    set({ copilotSheetOpen: open });
  },

  setChronicleOpen: (open) => {
    set({ chronicleOpen: open });
  },

  seedCopilotComposer: (text) => {
    const previous = get().copilotSeed;
    set({
      copilotSheetOpen: true,
      copilotSeed: { text, token: (previous?.token ?? 0) + 1 },
    });
  },

  resetCockpitUi: () => {
    set({ ...DEFAULTS });
  },
}));

/**
 * Resolve the signals stack's rendered state from the explicit preference (if any) and
 * the current alert pressure. Exported for tests; the stack is the only render-time
 * consumer.
 */
export function resolveSignalsState(
  preference: SignalsPreference | null,
  alertCount: number,
): SignalsPreference {
  return preference ?? (alertCount > 0 ? 'expanded' : 'capsule');
}
