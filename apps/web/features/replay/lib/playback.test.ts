import { describe, expect, it } from 'vitest';

import { clampSequence, nextSpeed, previousSpeed, speedToIntervalMs } from '@/features/replay/lib/playback';

describe('replay playback helpers', () => {
  it('maps speeds to intervals and disables continuous playback under reduced motion', () => {
    expect(speedToIntervalMs('1x', false)).toBe(800);
    expect(speedToIntervalMs('4x', false)).toBe(200);
    expect(speedToIntervalMs('1x', true)).toBe(Number.POSITIVE_INFINITY);
  });

  it('cycles speeds and clamps sequences', () => {
    expect(nextSpeed('1x')).toBe('2x');
    expect(previousSpeed('1x')).toBe('0.5x');
    expect(clampSequence(-5, 0, 100)).toBe(0);
    expect(clampSequence(999, 0, 100)).toBe(100);
  });
});
