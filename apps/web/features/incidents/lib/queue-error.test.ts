import { describe, expect, it } from 'vitest';

import { ApiClientError } from '@/lib/api/types';

import { describeQueueFailure } from './queue-error';

function apiError(status: number, code = 'ERROR', message = 'boom') {
  return new ApiClientError({ code, message, status });
}

describe('describeQueueFailure', () => {
  it('names an expired session and withholds a retry that cannot work', () => {
    const failure = describeQueueFailure(apiError(401, 'UNAUTHENTICATED'));
    expect(failure.kind).toBe('auth');
    expect(failure.retryable).toBe(false);
    expect(failure.title).toMatch(/session/i);
  });

  it('separates a permission refusal from an expired session', () => {
    const failure = describeQueueFailure(apiError(403, 'FORBIDDEN'));
    expect(failure.kind).toBe('permission');
    expect(failure.retryable).toBe(false);
  });

  it('marks throttling retryable and says to wait', () => {
    const failure = describeQueueFailure(apiError(429, 'RATE_LIMIT_EXCEEDED'));
    expect(failure.kind).toBe('throttled');
    expect(failure.retryable).toBe(true);
    expect(failure.message).toMatch(/wait/i);
  });

  it('reports a server fault as connectivity with its status', () => {
    const failure = describeQueueFailure(apiError(503, 'UNAVAILABLE'));
    expect(failure.kind).toBe('connectivity');
    expect(failure.message).toContain('503');
  });

  it('treats an unreachable API (raw fetch rejection) as connectivity, not data', () => {
    const failure = describeQueueFailure(new TypeError('Failed to fetch'));
    expect(failure.kind).toBe('connectivity');
    expect(failure.retryable).toBe(true);
  });

  it('surfaces the API message for a data-level rejection', () => {
    const failure = describeQueueFailure(apiError(422, 'VALIDATION_FAILED', 'bad payload'));
    expect(failure.kind).toBe('data');
    expect(failure.message).toBe('bad payload');
  });
});
