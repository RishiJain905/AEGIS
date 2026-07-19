import { describe, expect, it } from 'vitest';

import { parseReplaySequenceParam } from '@/features/replay/lib/deep-link';

describe('parseReplaySequenceParam', () => {
  it('parses a numeric sequence deep-link', () => {
    expect(parseReplaySequenceParam('120')).toBe(120);
    expect(parseReplaySequenceParam('0')).toBe(0);
  });

  it('takes the first value when the param repeats', () => {
    expect(parseReplaySequenceParam(['40', '99'])).toBe(40);
  });

  it('returns undefined for missing or empty values', () => {
    expect(parseReplaySequenceParam(undefined)).toBeUndefined();
    expect(parseReplaySequenceParam('')).toBeUndefined();
    expect(parseReplaySequenceParam([])).toBeUndefined();
  });

  it('rejects malformed or negative values', () => {
    expect(parseReplaySequenceParam('abc')).toBeUndefined();
    expect(parseReplaySequenceParam('-5')).toBeUndefined();
    expect(parseReplaySequenceParam('NaN')).toBeUndefined();
  });

  it('truncates decimals via base-10 integer parse', () => {
    expect(parseReplaySequenceParam('42.9')).toBe(42);
  });
});
