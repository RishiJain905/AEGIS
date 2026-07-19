/**
 * Shared presentation clock and per-edge activity tracking for the "alive
 * edges" treatment (redesign spec §7.9). Consumed by BOTH renderers — the
 * Sigma 2D edge program and the Three.js 3D edge materials — so their flow
 * animations share one time base and one pulse source.
 *
 * Everything here is presentation-only state: it never feeds back into
 * GraphStore, projections that tests hash, or any domain contract.
 */

const clockOrigin = typeof performance !== 'undefined' ? performance.now() : 0;

/** Seconds since module load, from one monotonic clock shared by all edge
 * animation (single shared time base — no per-edge clocks, no Date.now in
 * render state). */
export function getGraphAnimationTime(): number {
  if (typeof performance === 'undefined') {
    return 0;
  }
  return (performance.now() - clockOrigin) / 1000;
}

/** Sentinel meaning "this edge has never pulsed" — far enough in the past that
 * any decay function evaluates to zero. */
export const NO_PULSE = -1e6;

export interface EdgeActivitySample {
  id: string;
  eventCount: number;
}

/**
 * Tracks per-edge event activity across store syncs. An edge "pulses" on the
 * same sync tick its underlying relationship receives a new event (the
 * GraphStore delta application drives the sync — there is no polling here).
 * The first sync is treated as baseline so a snapshot load does not pulse the
 * whole graph at once.
 */
export class EdgeActivityTracker {
  private readonly counts = new Map<string, number>();
  private readonly pulseAt = new Map<string, number>();
  private baselined = false;

  update(edges: readonly EdgeActivitySample[]): void {
    const now = getGraphAnimationTime();
    const seen = new Set<string>();
    for (const edge of edges) {
      seen.add(edge.id);
      const previous = this.counts.get(edge.id);
      if (this.baselined && (previous === undefined || edge.eventCount > previous)) {
        this.pulseAt.set(edge.id, now);
      }
      this.counts.set(edge.id, edge.eventCount);
    }
    for (const id of this.counts.keys()) {
      if (!seen.has(id)) {
        this.counts.delete(id);
        this.pulseAt.delete(id);
      }
    }
    this.baselined = true;
  }

  getPulseAt(edgeId: string): number {
    return this.pulseAt.get(edgeId) ?? NO_PULSE;
  }

  clear(): void {
    this.counts.clear();
    this.pulseAt.clear();
    this.baselined = false;
  }
}

/** Deterministic per-edge phase offset in [0, 1) so flow pulses de-sync across
 * the graph without any randomness (stable across renders and sessions). */
export function edgeFlowPhase(edgeId: string): number {
  let hash = 0;
  for (let index = 0; index < edgeId.length; index += 1) {
    hash = (hash * 31 + edgeId.charCodeAt(index)) >>> 0;
  }
  return (hash % 997) / 997;
}
