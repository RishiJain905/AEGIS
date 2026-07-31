'use client';

import { useMemo } from 'react';

import type { TimelineEntryV1 } from '@aegis/contracts-ts';

import { useLiveRun } from '@/features/live-run/live-run-provider';

/**
 * Observable-activity cadence for the run — the companion to `use-threat-tempo`.
 *
 * The two answer different questions and are deliberately not merged. Threat tempo is the
 * fog reading: how much *undisclosed* attacker progress the server thinks has accrued, and
 * it says nothing about whether anything is reaching the operator. Activity is the opposite
 * side of the same coin: how much is landing on the desk right now, counted from the
 * sequenced events the client has actually received. Under fog an operator can watch a
 * silent graph for minutes and not know whether the attacker is working or the run is idle;
 * this is the signal that tells them which.
 *
 * Derived from the live timeline the reducer already maintains — no extra polling.
 */

export type ActivityLevel = 'quiet' | 'elevated' | 'active';

export interface ActivityReading {
  level: ActivityLevel;
  /** Weighted pressure score over the window; drives the level and the bar heights. */
  score: number;
  /** Raw event count inside the window. */
  count: number;
  /** Per-bucket weighted scores, oldest bucket first. */
  buckets: number[];
  /** Sim-seconds the window covers. */
  windowSeconds: number;
  /** Sim clock of the most recent counted event, or null when the window is empty. */
  lastSimTime: string | null;
}

/** Default observation window, in sim seconds. */
const WINDOW_SECONDS = 90;
const BUCKET_COUNT = 12;

/**
 * How loudly each kind of event registers. A status change or a reveal is the run telling
 * the operator something changed; ambient telemetry is background unless it failed.
 */
function eventWeight(eventType: string): number {
  if (eventType.startsWith('sim.hidden_condition.')) {
    return 5;
  }
  if (eventType === 'sim.asset.status_changed') {
    return 4;
  }
  if (eventType.startsWith('alert.') || eventType.startsWith('incident.')) {
    return 3;
  }
  if (eventType.startsWith('telemetry.')) {
    return eventType.includes('failed') ? 2 : 1;
  }
  // Agent chatter, risk recomputation and report progress are the platform working, not
  // the world changing — they must not make an idle run look busy.
  return 0;
}

function parseSimSeconds(timestamp: string): number | null {
  const parsed = Date.parse(timestamp);
  return Number.isNaN(parsed) ? null : parsed / 1000;
}

/**
 * Classify the run's observable cadence over the trailing window.
 *
 * Pure and exported so the thresholds are testable without a live socket. `now` is the sim
 * time the window ends at — normally the newest entry's timestamp, so a paused run keeps
 * showing the tempo it stopped at rather than decaying to quiet on wall-clock time.
 */
export function classifyActivity(
  entries: readonly Pick<TimelineEntryV1, 'eventType' | 'timestamp' | 'sequence'>[],
  options?: { windowSeconds?: number; bucketCount?: number },
): ActivityReading {
  const windowSeconds = options?.windowSeconds ?? WINDOW_SECONDS;
  const bucketCount = options?.bucketCount ?? BUCKET_COUNT;
  const buckets = Array.from({ length: bucketCount }, () => 0);

  const timed = entries
    .map((entry) => ({ entry, at: parseSimSeconds(entry.timestamp) }))
    .filter((row): row is { entry: (typeof entries)[number]; at: number } => row.at !== null);

  const newest = timed.at(-1)?.at ?? null;
  if (newest === null) {
    return {
      level: 'quiet',
      score: 0,
      count: 0,
      buckets,
      windowSeconds,
      lastSimTime: null,
    };
  }

  const windowStart = newest - windowSeconds;
  const bucketSeconds = windowSeconds / bucketCount;
  let score = 0;
  let count = 0;
  let lastSimTime: string | null = null;

  for (const { entry, at } of timed) {
    if (at < windowStart) {
      continue;
    }
    const weight = eventWeight(entry.eventType);
    if (weight === 0) {
      continue;
    }
    score += weight;
    count += 1;
    lastSimTime = entry.timestamp;
    const index = Math.min(
      bucketCount - 1,
      Math.max(0, Math.floor((at - windowStart) / bucketSeconds)),
    );
    buckets[index] = (buckets[index] ?? 0) + weight;
  }

  const level: ActivityLevel = score >= 14 ? 'active' : score >= 4 ? 'elevated' : 'quiet';
  return { level, score, count, buckets, windowSeconds, lastSimTime };
}

export const ACTIVITY_COPY: Record<ActivityLevel, { label: string; detail: string }> = {
  quiet: {
    label: 'Quiet',
    detail: 'Nothing is moving on the floor. Absence of signal is not absence of activity.',
  },
  elevated: {
    label: 'Elevated',
    detail: 'The run is producing signal. Worth a look before it compounds.',
  },
  active: {
    label: 'Active',
    detail: 'Something is happening right now. Work the newest alert first.',
  },
};

/**
 * Live activity reading for the current run, or a quiet reading when there is no live run.
 */
export function useRunActivity(options?: { windowSeconds?: number }): ActivityReading {
  const liveRun = useLiveRun();
  const entries = liveRun?.state.timelineEntries ?? [];
  const windowSeconds = options?.windowSeconds;

  return useMemo(
    () => classifyActivity(entries, windowSeconds ? { windowSeconds } : undefined),
    [entries, windowSeconds],
  );
}
