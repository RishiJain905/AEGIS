/**
 * BUG-003: a session accumulated ~391 failed requests against a dead API. The policy has
 * to bound both halves of that — how many times one request is retried, and how fast a
 * failing poll comes back.
 */
import { describe, expect, it } from 'vitest';

import { ApiClientError } from '@/lib/api/types';
import {
  MAX_POLL_INTERVAL_MS,
  MAX_QUERY_RETRIES,
  RETRY_MAX_DELAY_MS,
  isRetryableError,
  pollIntervalWhileHealthy,
  queryRetryDelayMs,
  shouldRetryQuery,
} from '@/lib/api/retry-policy';

function apiError(status: number): ApiClientError {
  return new ApiClientError({ code: 'HTTP_ERROR', message: 'failed', status });
}

describe('retry eligibility', () => {
  it('does not retry statuses that a second attempt cannot change', () => {
    for (const status of [400, 401, 403, 404, 405, 409, 410, 422]) {
      expect(isRetryableError(apiError(status))).toBe(false);
    }
  });

  it('retries server faults, rate limits and requests that never got a response', () => {
    for (const status of [429, 500, 502, 503, 504]) {
      expect(isRetryableError(apiError(status))).toBe(true);
    }
    expect(isRetryableError(new TypeError('Failed to fetch'))).toBe(true);
  });

  it('stops at the attempt cap however transient the fault looks', () => {
    expect(shouldRetryQuery(MAX_QUERY_RETRIES - 1, apiError(503))).toBe(true);
    expect(shouldRetryQuery(MAX_QUERY_RETRIES, apiError(503))).toBe(false);
  });

  it('does not spend the retry budget on a permission failure', () => {
    expect(shouldRetryQuery(0, apiError(403))).toBe(false);
  });
});

describe('retry delay', () => {
  it('grows with the attempt and never exceeds the ceiling', () => {
    const noJitter = () => 1;
    const [first, second, third] = [0, 1, 2].map((attempt) =>
      queryRetryDelayMs(attempt, noJitter),
    ) as [number, number, number];

    expect(first).toBeLessThan(second);
    expect(second).toBeLessThan(third);
    for (const delay of [first, second, third, queryRetryDelayMs(40, noJitter)]) {
      expect(delay).toBeLessThanOrEqual(RETRY_MAX_DELAY_MS);
    }
  });

  it('jitters within [0, backoff] so simultaneous queries do not retry in lockstep', () => {
    const ceiling = queryRetryDelayMs(3, () => 1);
    expect(queryRetryDelayMs(3, () => 0)).toBe(0);
    for (const draw of [0.1, 0.5, 0.9]) {
      const delay = queryRetryDelayMs(3, () => draw);
      expect(delay).toBeGreaterThanOrEqual(0);
      expect(delay).toBeLessThanOrEqual(ceiling);
    }
  });
});

describe('polling interval', () => {
  const interval = pollIntervalWhileHealthy(6_000);

  it('keeps the healthy cadence while the query is succeeding', () => {
    expect(interval({ state: { status: 'success', errorUpdateCount: 0 } })).toBe(6_000);
  });

  it('backs off while the query is failing, up to a ceiling', () => {
    const first = interval({ state: { status: 'error', errorUpdateCount: 1 } });
    const later = interval({ state: { status: 'error', errorUpdateCount: 4 } });

    expect(first).toBeGreaterThan(6_000);
    expect(later).toBeGreaterThan(first);
    expect(interval({ state: { status: 'error', errorUpdateCount: 99 } })).toBe(
      MAX_POLL_INTERVAL_MS,
    );
  });

  it('snaps back to the healthy cadence once the query recovers', () => {
    expect(interval({ state: { status: 'success', errorUpdateCount: 7 } })).toBe(6_000);
  });
});
