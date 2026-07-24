import { describe, expect, it } from 'vitest';

import {
  computeZoneHullRect,
  rollupZoneThreat,
} from '@/features/operational-graph/rendering/zone-overlay';
import {
  REVEAL_PULSE_MS,
  revealPulseProgress,
} from '@/features/operational-graph/rendering/signal-overlay';

describe('rollupZoneThreat', () => {
  it('escalates to hostile on any compromised member', () => {
    expect(rollupZoneThreat(['normal', 'suspicious', 'compromised'])).toBe('hostile');
  });

  it('marks watch for suspicious or under-investigation members', () => {
    expect(rollupZoneThreat(['normal', 'suspicious'])).toBe('watch');
    expect(rollupZoneThreat(['normal', 'under_investigation'])).toBe('watch');
  });

  it('keeps contained below watch and normal at none', () => {
    expect(rollupZoneThreat(['normal', 'contained'])).toBe('contained');
    expect(rollupZoneThreat(['contained', 'suspicious'])).toBe('watch');
    expect(rollupZoneThreat(['normal', 'normal'])).toBe('none');
    expect(rollupZoneThreat([])).toBe('none');
  });
});

describe('computeZoneHullRect', () => {
  it('pads the bounding box by the padding plus the largest node radius', () => {
    const rect = computeZoneHullRect(
      [
        { x: 100, y: 100, sizePx: 10 },
        { x: 200, y: 160, sizePx: 6 },
      ],
      20,
    );
    expect(rect).toEqual({ left: 70, top: 70, width: 160, height: 120 });
  });

  it('returns null when a zone has no visible members', () => {
    expect(computeZoneHullRect([], 20)).toBeNull();
  });
});

describe('revealPulseProgress', () => {
  it('runs 0..1 over the pulse lifetime and clamps at both ends', () => {
    expect(revealPulseProgress(1000, 1000)).toBe(0);
    expect(revealPulseProgress(1000 + REVEAL_PULSE_MS / 2, 1000)).toBeCloseTo(0.5);
    expect(revealPulseProgress(1000 + REVEAL_PULSE_MS * 2, 1000)).toBe(1);
    expect(revealPulseProgress(500, 1000)).toBe(0);
  });
});
