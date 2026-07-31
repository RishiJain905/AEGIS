import { create } from 'zustand';

/**
 * Optimistic acknowledgment for a control the operator just ordered.
 *
 * The durable answer already exists — the graph node carries `appliedControls`, and the
 * inspector badges them — but it arrives over the event stream a beat later. In that gap the
 * operator who just put an asset under observation sees nothing change, which reads as "the
 * click did nothing". This holds the order between the accepted API response and the control
 * landing on the node, so the inspector can say so.
 *
 * Deliberately not persisted and deliberately not authoritative: it is cleared the moment the
 * real control shows up, and on any run change, so a stale acknowledgment can never outlive
 * the fact it was anticipating.
 */

export interface PendingControl {
  assetId: string;
  /** The command's own label, as the operator saw it on the menu ("Observe"). */
  label: string;
  /** Wall-clock ms when the order was accepted, for the staleness sweep. */
  at: number;
}

/** How long an unconfirmed acknowledgment may linger before it stops being informative. */
export const PENDING_CONTROL_TTL_MS = 30_000;

interface PendingControlState {
  runId: string | null;
  pending: Record<string, PendingControl>;
  /** Record an accepted order. Switching runs drops everything the previous run pended. */
  note: (runId: string, assetId: string, label: string) => void;
  /** Drop the acknowledgment — the real control landed, or it went stale. */
  clear: (assetId: string) => void;
}

export const usePendingControlStore = create<PendingControlState>()((set, get) => ({
  runId: null,
  pending: {},

  note: (runId, assetId, label) => {
    const sameRun = get().runId === runId;
    set((state) => ({
      runId,
      pending: {
        ...(sameRun ? state.pending : {}),
        [assetId]: { assetId, label, at: Date.now() },
      },
    }));
  },

  clear: (assetId) => {
    if (!(assetId in get().pending)) {
      return;
    }
    set((state) => ({
      pending: Object.fromEntries(Object.entries(state.pending).filter(([key]) => key !== assetId)),
    }));
  },
}));

/** Whether an acknowledgment is still worth showing. */
export function isPendingControlFresh(pending: PendingControl, now: number = Date.now()): boolean {
  return now - pending.at < PENDING_CONTROL_TTL_MS;
}
