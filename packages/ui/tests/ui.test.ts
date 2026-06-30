import { describe, expect, it } from 'vitest';
import { formatPlatformStatus } from '../src/index';

describe('formatPlatformStatus', () => {
  it('includes service name and workspace version', () => {
    expect(formatPlatformStatus('web')).toMatch(/^web@/);
  });
});
