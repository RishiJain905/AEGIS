import type { DomainEventEnvelopeV1 } from '@aegis/contracts-ts';
import { domainEventEnvelopeSchema, parseContract } from '@aegis/contracts-ts';

import { apiFetch } from '@/lib/api/auth-fetch';
import { ApiClientError } from '@/lib/api/types';

/** Events the server returns per request. Matches the endpoint's own maximum. */
export const EVENT_PAGE_LIMIT = 500;

/**
 * Hard stop on how many pages one catch-up may walk.
 *
 * A run that has been unattended for a long time can be many thousands of events ahead, but
 * an unbounded loop here is a request amplifier if the server ever stops advancing the
 * cursor. The no-progress guard below is the correctness check; this is the backstop.
 */
const MAX_CATCH_UP_PAGES = 40;

export async function fetchRunEvents(
  runId: string,
  fromSequence: number,
  signal?: AbortSignal,
): Promise<DomainEventEnvelopeV1[]> {
  const params = new URLSearchParams({
    from_sequence: String(fromSequence),
    limit: String(EVENT_PAGE_LIMIT),
  });
  const response = await apiFetch(`/api/v1/realtime/runs/${runId}/events?${params.toString()}`, {
    signal,
  });
  if (!response.ok) {
    throw new ApiClientError({
      code: 'HTTP_ERROR',
      message: `Failed to fetch run events: ${String(response.status)}`,
      status: response.status,
    });
  }
  const body: unknown = await response.json();
  if (
    typeof body !== 'object' ||
    body === null ||
    !('events' in body) ||
    !Array.isArray((body as { events: unknown }).events)
  ) {
    throw new Error('Invalid run events response');
  }
  return (body as { events: unknown[] }).events.map((event) =>
    parseContract(domainEventEnvelopeSchema, event),
  );
}

/**
 * Every persisted event in `[fromSequence, toSequence]`, across as many pages as it takes.
 *
 * The single-page version of this silently truncated at {@link EVENT_PAGE_LIMIT}: a client
 * more than one page behind its run never reached the head, so the next live event always
 * looked like a sequence gap, which triggered another resync — a loop that only ever fell
 * further behind. Paging until the range is covered is what makes "caught up" true.
 */
export async function fetchMissingEvents(
  runId: string,
  fromSequence: number,
  toSequence: number,
  signal?: AbortSignal,
): Promise<DomainEventEnvelopeV1[]> {
  const collected: DomainEventEnvelopeV1[] = [];
  let cursor = fromSequence;

  for (let page = 0; page < MAX_CATCH_UP_PAGES && cursor <= toSequence; page += 1) {
    const events = await fetchRunEvents(runId, cursor, signal);
    if (events.length === 0) {
      break;
    }

    let highestSequence = cursor - 1;
    for (const event of events) {
      highestSequence = Math.max(highestSequence, event.sequence);
      // Strictly the range the caller asked for. Anything below `fromSequence` is already
      // applied, and re-applying it would move the cursor backwards.
      if (event.sequence >= fromSequence && event.sequence <= toSequence) {
        collected.push(event);
      }
    }

    // The server did not advance past where we asked from; another identical request would
    // return the same page forever.
    if (highestSequence < cursor) {
      break;
    }
    cursor = highestSequence + 1;

    // A short page means the server has nothing further to give, whatever the head claims.
    if (events.length < EVENT_PAGE_LIMIT) {
      break;
    }
  }

  return collected;
}
