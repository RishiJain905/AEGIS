/**
 * Post-run event-stream loader for the adversary dossier.
 *
 * Pages the authoritative history endpoint (`/api/v1/realtime/runs/{id}/events`) to
 * completion and coerces each record into the lenient {@link DossierEvent} shape. We use a
 * defensive coercion rather than the strict `domainEventEnvelopeSchema` on purpose: the
 * server emits event types the TS contract registry has not yet enumerated (Phase 7
 * operator/autonomy/report events), and a strict parse would reject the entire batch when
 * one unknown type appears. The dossier tolerates unknown types — it simply ignores the
 * ones it has no lane for.
 */

import { apiFetchJson } from '@/lib/api/auth-fetch';

import type { DossierEvent } from './assemble-dossier';

const PAGE_SIZE = 500;
// Hard ceiling so a pathological run can never spin the loader forever. A 300-step run
// emits well under this; runs beyond it truncate to the earliest events (the campaign
// origin), which is the debrief's most important window.
const MAX_EVENTS = 20_000;

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function coerceActorRef(value: unknown): { type: string; id: string } {
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return { type: asString(record.type), id: asString(record.id) };
  }
  return { type: '', id: '' };
}

/** Coerce one raw event record into a DossierEvent, or null if it lacks a usable shape. */
export function coerceDossierEvent(raw: unknown): DossierEvent | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const sequence = record.sequence;
  const type = record.type;
  if (typeof sequence !== 'number' || typeof type !== 'string' || type.length === 0) {
    return null;
  }
  const actor = coerceActorRef(record.actor);
  const subject = coerceActorRef(record.subject);
  const payload =
    record.payload && typeof record.payload === 'object'
      ? (record.payload as Record<string, unknown>)
      : {};
  return {
    sequence,
    type,
    simTime: asString(record.simTime),
    actorType: actor.type,
    actorId: actor.id,
    subjectType: subject.type,
    subjectId: subject.id,
    payload,
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

/**
 * Fetch every event for a run, paging by sequence. Callers MUST only invoke this for a
 * terminated run — the stream is full ground truth and would leak the attacker's position
 * during a live run.
 */
export async function fetchAllRunEvents(
  runId: string,
  signal?: AbortSignal,
): Promise<DossierEvent[]> {
  const collected: DossierEvent[] = [];
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
      const coerced = coerceDossierEvent(raw);
      if (coerced) {
        collected.push(coerced);
      }
      if (coerced && coerced.sequence > maxSequence) {
        maxSequence = coerced.sequence;
      } else if (
        !coerced &&
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
    // Advance strictly past the highest sequence seen to avoid re-fetching the boundary.
    const nextFrom = maxSequence + 1;
    if (nextFrom <= fromSequence) {
      break; // no forward progress — guard against a stuck cursor
    }
    fromSequence = nextFrom;
  }

  return collected.sort((a, b) => a.sequence - b.sequence);
}
