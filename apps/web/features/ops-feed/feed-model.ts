/**
 * Pure ops-feed transform: raw feed entries -> ordered, collapsed render rows.
 *
 * Kept React-free and total so the collapse/ordering rules are unit-testable in isolation.
 * The feed arrives ascending by sequence; the room reads newest-first, autonomous "nothing
 * changed" checks collapse into a single quiet row, and detections are never hidden.
 */

import type { RunFeedEntry } from '@/features/command-surface';

export type FeedRow =
  | {
      kind: 'entry';
      key: string;
      entry: RunFeedEntry;
      detection: boolean;
      biasCheck: boolean;
    }
  | { kind: 'collapsed'; key: string; entries: RunFeedEntry[]; count: number };

function payloadString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === 'string' ? value.toLowerCase() : null;
}

const NO_CHANGE_TOKENS = new Set(['no_change', 'nochange', 'unchanged']);

/**
 * A routine autonomous "nothing to report" finding — the kind we collapse so the feed keeps
 * signal. Defensive against a still-settling payload shape: an agent finding originated by
 * autonomy where any conventional no-change marker is present.
 */
export function isNoChangeAutonomyReport(entry: RunFeedEntry): boolean {
  if (entry.category !== 'agent' || entry.initiator !== 'autonomy') {
    return false;
  }
  const p = entry.payload;
  if (p['noChange'] === true || p['no_change'] === true) {
    return true;
  }
  for (const key of ['outcome', 'disposition', 'status']) {
    const token = payloadString(p, key);
    if (token !== null && NO_CHANGE_TOKENS.has(token)) {
      return true;
    }
  }
  return (
    entry.summary.toLowerCase().includes('no_change') ||
    entry.type.toLowerCase().includes('no_change')
  );
}

/** A reveal/detection moment — the dramatic beat that must never be collapsed or muted. */
export function isDetection(entry: RunFeedEntry): boolean {
  return entry.category === 'reveal' || entry.type.includes('hidden_condition.revealed');
}

/**
 * A bias-guard finding — an autonomous ORACLE beat that re-examined a leading hypothesis
 * against contradicting evidence. Rendered as a distinct "BIAS CHECK" beat so the operator
 * notices their working theory being challenged (a no-change bias check still collapses).
 */
export function isBiasCheck(entry: RunFeedEntry): boolean {
  if (entry.category !== 'agent' || entry.initiator !== 'autonomy') {
    return false;
  }
  const haystacks = [entry.summary.toLowerCase(), entry.type.toLowerCase()];
  const p = entry.payload;
  for (const key of ['kind', 'taskKind', 'origin', 'reason']) {
    const token = payloadString(p, key);
    if (token !== null) {
      haystacks.push(token);
    }
  }
  return haystacks.some((text) => text.includes('bias') || text.includes('contradict'));
}

/**
 * Build newest-first render rows, collapsing runs of routine autonomy no-change reports.
 * Detections are always standalone `entry` rows flagged `detection: true`.
 */
export function buildFeedRows(entries: RunFeedEntry[]): FeedRow[] {
  const ordered = [...entries].sort((a, b) => b.sequence - a.sequence);
  const rows: FeedRow[] = [];
  let pendingNoChange: RunFeedEntry[] = [];

  const flush = () => {
    const group = pendingNoChange;
    pendingNoChange = [];
    const first = group[0];
    if (!first) {
      return;
    }
    if (group.length === 1) {
      rows.push({
        kind: 'entry',
        key: first.eventId,
        entry: first,
        detection: false,
        biasCheck: false,
      });
    } else {
      rows.push({
        kind: 'collapsed',
        key: `collapsed-${first.eventId}`,
        entries: group,
        count: group.length,
      });
    }
  };

  for (const entry of ordered) {
    if (isNoChangeAutonomyReport(entry)) {
      pendingNoChange.push(entry);
      continue;
    }
    flush();
    rows.push({
      kind: 'entry',
      key: entry.eventId,
      entry,
      detection: isDetection(entry),
      biasCheck: isBiasCheck(entry),
    });
  }
  flush();
  return rows;
}

/** The most recent detection entry, if any — used for the aria-live announcement. */
export function latestDetection(entries: RunFeedEntry[]): RunFeedEntry | null {
  let latest: RunFeedEntry | null = null;
  for (const entry of entries) {
    if (isDetection(entry) && (latest === null || entry.sequence > latest.sequence)) {
      latest = entry;
    }
  }
  return latest;
}
