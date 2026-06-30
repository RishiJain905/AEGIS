import { describe, expect, it } from 'vitest';
import { formatPlatformStatus } from '@aegis/ui';

describe('web workspace wiring', () => {
  it('can format platform status via ui package', () => {
    expect(formatPlatformStatus('web')).toContain('web@');
  });
});
