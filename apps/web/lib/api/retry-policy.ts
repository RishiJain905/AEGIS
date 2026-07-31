/**
 * One retry policy for every HTTP query in the console.
 *
 * QA watched a single session accumulate roughly 391 failed requests against a dead API.
 * Nothing here retried without a bound — the multiplier was that half a dozen hooks poll
 * on 2.5-6 second intervals, each poll spent its full retry budget, and a failing poll
 * kept its interval, so the load *rose* exactly when the server could least take it. Two
 * rules fix that: retries back off with jitter to a hard ceiling, and a query that is
 * currently failing polls progressively more slowly until it recovers.
 *
 * The websocket transport already does the equivalent
 * (`packages/realtime-client/src/reconnect.ts`); this is the same discipline for HTTP.
 */

import { ApiClientError } from '@/lib/api/types';

/** Attempts after the first. Three tries total for a transient fault. */
export const MAX_QUERY_RETRIES = 2;
export const RETRY_BASE_DELAY_MS = 500;
export const RETRY_MAX_DELAY_MS = 30_000;

/** How far a failing poll's interval is allowed to stretch before it stops growing. */
export const MAX_POLL_INTERVAL_MS = 60_000;

/**
 * Statuses where the answer will not change by asking again: the request itself is the
 * problem (shape, permission, or a resource that is gone), so a retry only burns rate
 * limit. 429 is deliberately absent — it is retryable, just not immediately.
 */
const NON_RETRYABLE_STATUSES = new Set([400, 401, 403, 404, 405, 409, 410, 422]);

export function isRetryableError(error: unknown): boolean {
  if (error instanceof ApiClientError) {
    return !NON_RETRYABLE_STATUSES.has(error.status);
  }
  // No response reached us at all (network failure, CORS rejection, abort). Transient
  // until proven otherwise, and the attempt cap bounds how long we believe that.
  return true;
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_QUERY_RETRIES && isRetryableError(error);
}

/**
 * Full jitter: a delay drawn uniformly from `[0, exponential backoff]`, capped.
 *
 * Jitter matters more here than the backoff does. A run workspace mounts a dozen queries
 * at once, so a deterministic delay marches all of them back to the server in the same
 * millisecond, repeatedly — the retry storm arrives as a thundering herd.
 */
export function queryRetryDelayMs(
  attemptIndex: number,
  random: () => number = Math.random,
): number {
  const ceiling = Math.min(RETRY_MAX_DELAY_MS, RETRY_BASE_DELAY_MS * 2 ** attemptIndex);
  return Math.round(random() * ceiling);
}

/**
 * A `refetchInterval` that stretches while the query is failing and snaps back on success.
 *
 * Pass the healthy cadence: while the query is erroring the interval doubles per failed
 * fetch up to {@link MAX_POLL_INTERVAL_MS}, so a poll against a dead endpoint decays to
 * once a minute instead of hammering it every few seconds forever. A success returns the
 * cadence to `baseMs` immediately.
 *
 * The counter is `errorUpdateCount`, which query-core increments once per errored fetch and
 * — unlike `fetchFailureCount`, which resets at the start of every fetch and so never
 * exceeds the retry budget — does not reset on recovery. The practical consequence is worth
 * knowing: a query that failed a lot earlier in the session re-enters backoff near the
 * ceiling on its next failure rather than climbing again from `baseMs`. That is the safe
 * direction to be wrong in — it can only ever poll a proven-flaky endpoint *less* often,
 * never more — and healthy polling is unaffected because the error branch is not taken.
 */
export function pollIntervalWhileHealthy(baseMs: number) {
  return (query: { state: { status: string; errorUpdateCount: number } }): number => {
    if (query.state.status !== 'error') {
      return baseMs;
    }
    const failedFetches = Math.max(1, query.state.errorUpdateCount);
    return Math.min(MAX_POLL_INTERVAL_MS, baseMs * 2 ** failedFetches);
  };
}
