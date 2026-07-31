'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchSnapshotBootstrap } from '@/lib/realtime/snapshot-resync';
import { pollIntervalWhileHealthy } from '@/lib/api/retry-policy';

export interface ThreatTempoReading {
  /** Ambient pressure scalar in [0, 1], or null when the run has no fog tension. */
  tempo: number | null;
  /**
   * Whether the run's capability loadout enables the indicator. Defaults to true when no
   * loadout is present on the run (the indicator shows by default).
   */
  loadoutEnabled: boolean;
}

/**
 * Poll the run's fog-of-war threat-tempo scalar (0..1) from the bootstrap payload.
 *
 * The tempo is an ambient pressure reading derived server-side from undisclosed-vs-disclosed
 * attacker progress; it carries no asset or condition identity. We read it on a modest
 * cadence (the server recomputes it each tick) rather than over the sequenced event stream,
 * which is intentionally reserved for authoritative domain events. The loadout gate is read
 * defensively from the same payload so a run that never opted into threat tempo can hide it.
 */
export function useThreatTempo(runId: string, options?: { enabled?: boolean }) {
  return useQuery<ThreatTempoReading>({
    queryKey: ['runs', runId, 'threat-tempo'],
    queryFn: async ({ signal }): Promise<ThreatTempoReading> => {
      const bootstrap = await fetchSnapshotBootstrap(runId, signal);
      // Read the loadout flag defensively: the loadout contract is optional and may be
      // absent on the run at runtime. Absent/undefined → show by default; only an explicit
      // `false` hides the indicator.
      const loadout = (bootstrap.run as { loadout?: { threatTempo?: boolean } }).loadout;
      return {
        tempo: bootstrap.threatTempo ?? null,
        loadoutEnabled: loadout?.threatTempo !== false,
      };
    },
    enabled: (options?.enabled ?? true) && Boolean(runId),
    refetchInterval: pollIntervalWhileHealthy(5_000),
    // Ambient indicator — a missed poll should never surface an error state.
    retry: false,
  });
}
