import { describe, expect, it } from 'vitest';

import { labelPriority, selectNonCollidingLabels, type LabelCandidate } from './label-topcoat';

function rect(left: number, top: number, width = 60, height = 20) {
  return { left, top, width, height };
}

describe('selectNonCollidingLabels', () => {
  it('keeps every candidate when nothing overlaps', () => {
    const candidates: LabelCandidate[] = [
      { id: 'a', priority: 1, rect: rect(0, 0) },
      { id: 'b', priority: 1, rect: rect(200, 0) },
      { id: 'c', priority: 1, rect: rect(400, 0) },
    ];
    expect(selectNonCollidingLabels(candidates)).toEqual(new Set(['a', 'b', 'c']));
  });

  it('drops the lower-priority label of an overlapping pair, keeping the higher one whole', () => {
    // Same footprint, wildly different priority (e.g. a selected node vs a plain one).
    const candidates: LabelCandidate[] = [
      { id: 'low', priority: 1, rect: rect(0, 0) },
      { id: 'high', priority: 100, rect: rect(10, 0) }, // overlaps 'low'
    ];
    expect(selectNonCollidingLabels(candidates)).toEqual(new Set(['high']));
  });

  it('breaks priority ties by input order (stable)', () => {
    const candidates: LabelCandidate[] = [
      { id: 'first', priority: 5, rect: rect(0, 0) },
      { id: 'second', priority: 5, rect: rect(10, 0) }, // overlaps 'first'
    ];
    expect(selectNonCollidingLabels(candidates)).toEqual(new Set(['first']));
  });

  it('does not let one kept label block two others that do not overlap each other', () => {
    // 'left' and 'right' both overlap 'center' (high priority, kept) but not each other -
    // both should still be dropped since each individually collides with the kept label.
    const candidates: LabelCandidate[] = [
      { id: 'center', priority: 100, rect: rect(100, 0, 60, 20) },
      { id: 'left', priority: 1, rect: rect(90, 0, 60, 20) },
      { id: 'right', priority: 1, rect: rect(140, 0, 60, 20) },
      { id: 'far', priority: 1, rect: rect(500, 0, 60, 20) },
    ];
    expect(selectNonCollidingLabels(candidates)).toEqual(new Set(['center', 'far']));
  });
});

describe('labelPriority', () => {
  const base = { color: '#fff', size: 10 };

  it('ranks explicit emphasis above plain size', () => {
    expect(labelPriority({ ...base, selected: true })).toBeGreaterThan(
      labelPriority({ ...base, riskBand: 'critical' }),
    );
    expect(labelPriority({ ...base, hovered: true })).toBeGreaterThan(
      labelPriority({ ...base, incidentMarked: true }),
    );
    expect(labelPriority({ ...base, incidentMarked: true })).toBeGreaterThan(
      labelPriority({ ...base, evidenceMarked: true }),
    );
    expect(labelPriority({ ...base, riskBand: 'critical' })).toBeGreaterThan(
      labelPriority({ ...base, riskBand: 'high' }),
    );
  });

  it('falls back to node size when nothing is emphasized', () => {
    expect(labelPriority({ ...base, size: 20 })).toBeGreaterThan(
      labelPriority({ ...base, size: 5 }),
    );
  });

  it('keeps the size fallback well below every emphasis tier', () => {
    // Otherwise an unusually large ordinary node could outrank real emphasis.
    expect(labelPriority({ ...base, size: 1000 })).toBeLessThan(
      labelPriority({ ...base, riskBand: 'high' }),
    );
  });
});
