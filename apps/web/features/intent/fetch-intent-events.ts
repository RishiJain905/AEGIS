/**
 * Minimal, self-contained event-stream loader for the commander's-intent review.
 *
 * Pages the authoritative history endpoint to completion (capped) and returns a lenient event
 * shape. Kept independent of other features' loaders so features/intent has no cross-feature
 * coupling. Callers MUST only invoke this for a terminated run — the stream is ground truth and
 * would leak the attacker's position during a live run.
 */

import { apiFetchJson } from '@/lib/api/auth-fetch';

export interface IntentEvent {
  eventId: string;
  sequence: number;
  type: string;
  assetId: string;
  command: string;
  /** Asset status from a `sim.asset.status_changed` payload, when present. */
  status: string;
  label: string;
}

const PAGE_SIZE = 500;
const MAX_EVENTS = 20_000;

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function assetIdOf(payload: Record<string, unknown>, subjectId: string): string {
  for (const key of ['assetId', 'targetAssetId', 'sourceAssetId', 'entityId']) {
    const value = payload[key];
    if (typeof value === 'string' && value.length > 0) {
      return value;
    }
  }
  return subjectId.startsWith('asset:') ? subjectId : '';
}

/** Coerce one raw event record into an IntentEvent, or null if it lacks a usable shape. */
export function coerceIntentEvent(raw: unknown): IntentEvent | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const sequence = record.sequence;
  const type = record.type;
  if (typeof sequence !== 'number' || typeof type !== 'string' || type.length === 0) {
    return null;
  }
  const payload =
    record.payload && typeof record.payload === 'object'
      ? (record.payload as Record<string, unknown>)
      : {};
  const subject =
    record.subject && typeof record.subject === 'object'
      ? (record.subject as Record<string, unknown>)
      : {};
  return {
    eventId: asString(record.eventId, `evt-${String(sequence)}`),
    sequence,
    type,
    assetId: assetIdOf(payload, asString(subject.id)),
    command: asString(payload.command),
    status: asString(payload.status),
    label: asString(payload.label) || asString(payload.title) || asString(payload.status),
  };
}

function extractEvents(body: unknown): unknown[] {
  if (body && typeof body === 'object' && 'events' in body) {
    const events = (body as { events: unknown }).events;
    if (Array.isArray(events)) {
      return events;
    }
  }
  return [];
}

/** Fetch every event for a terminated run, paging by sequence (capped). */
export async function fetchIntentEvents(
  runId: string,
  signal?: AbortSignal,
): Promise<IntentEvent[]> {
  const collected: IntentEvent[] = [];
  let fromSequence = 0;

  for (;;) {
    const params = new URLSearchParams({
      from_sequence: String(fromSequence),
      limit: String(PAGE_SIZE),
    });
    const body = await apiFetchJson<unknown>(
      `/api/v1/realtime/runs/${encodeURIComponent(runId)}/events?${params.toString()}`,
      { signal },
    );
    const rawEvents = extractEvents(body);
    if (rawEvents.length === 0) {
      break;
    }
    let maxSequence = fromSequence;
    for (const raw of rawEvents) {
      const coerced = coerceIntentEvent(raw);
      if (coerced) {
        collected.push(coerced);
        maxSequence = Math.max(maxSequence, coerced.sequence);
      } else if (
        raw &&
        typeof raw === 'object' &&
        typeof (raw as Record<string, unknown>).sequence === 'number'
      ) {
        maxSequence = Math.max(maxSequence, (raw as { sequence: number }).sequence);
      }
    }
    if (rawEvents.length < PAGE_SIZE || collected.length >= MAX_EVENTS) {
      break;
    }
    const nextFrom = maxSequence + 1;
    if (nextFrom <= fromSequence) {
      break;
    }
    fromSequence = nextFrom;
  }

  return collected.sort((a, b) => a.sequence - b.sequence);
}
