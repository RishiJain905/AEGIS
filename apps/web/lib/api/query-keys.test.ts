import { describe, expect, it } from 'vitest';

import { queryKeys } from '@/lib/api/query-keys';

describe('queryKeys', () => {
  it('builds stable run detail keys', () => {
    expect(queryKeys.runs.detail('run_123')).toEqual(['runs', 'run_123']);
  });

  it('builds nested incident keys under runs', () => {
    expect(queryKeys.runs.incidents('run_123')).toEqual(['runs', 'run_123', 'incidents']);
  });
});
