import { describe, expect, it } from 'vitest';

import { computeReconnectDelayMs } from '../src/reconnect';

describe('computeReconnectDelayMs', () => {
  it('returns bounded jittered delay', () => {
    const delay = computeReconnectDelayMs(3, {
      minDelayMs: 100,
      maxDelayMs: 1000,
      multiplier: 2,
      jitterRatio: 0,
    });
    expect(delay).toBe(400);
  });

  it('never returns below minDelayMs', () => {
    const delay = computeReconnectDelayMs(1, { minDelayMs: 500, jitterRatio: 0 });
    expect(delay).toBeGreaterThanOrEqual(500);
  });
});
