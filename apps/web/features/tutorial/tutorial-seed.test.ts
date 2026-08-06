import { describe, expect, it } from 'vitest';

import { LEGACY_TRAINING_SEED, deriveTrainingSeed } from './tutorial-seed';

describe('deriveTrainingSeed', () => {
  it('is stable per identity, so relaunching resolves to the same run id', () => {
    expect(deriveTrainingSeed('user:operator-alpha')).toBe(
      deriveTrainingSeed('user:operator-alpha'),
    );
  });

  it('stays inside the server’s random-seed range [1, 2^31-1]', () => {
    for (const userId of [
      'user:operator-alpha',
      'user:admin-alpha',
      'user:acct_9020b4189b4c9d8b620eb455',
    ]) {
      const seed = deriveTrainingSeed(userId);
      expect(seed).toBeGreaterThanOrEqual(1);
      expect(seed).toBeLessThanOrEqual(2 ** 31 - 1);
    }
  });

  it('gives different operators different seeds, so no two operators share a run id', () => {
    expect(deriveTrainingSeed('user:operator-alpha')).not.toBe(
      deriveTrainingSeed('user:admin-alpha'),
    );
  });

  it('falls back to the legacy shared seed when there is no authenticated actor', () => {
    expect(deriveTrainingSeed(null)).toBe(LEGACY_TRAINING_SEED);
  });
});
