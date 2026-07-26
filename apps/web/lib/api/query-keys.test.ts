import { describe, expect, it } from 'vitest';

import { queryKeys } from '@/lib/api/query-keys';

describe('queryKeys', () => {
  it('builds stable run detail keys', () => {
    expect(queryKeys.runs.detail('run_123')).toEqual(['runs', 'run_123']);
  });

  it('builds nested incident keys under runs', () => {
    expect(queryKeys.runs.incidents('run_123')).toEqual(['runs', 'run_123', 'incidents']);
  });

  it('nests the origin-filtered agent session key under the unfiltered one', () => {
    // The realtime `agent.*` handler invalidates the unfiltered key. TanStack matches
    // by prefix, so the filtered variant must extend it — otherwise the copilot's
    // operator-scoped list would never refresh on a live event.
    const unfiltered = queryKeys.agentSessions.listForRun('run_123');
    const operator = queryKeys.agentSessions.listForRun('run_123', 'operator');

    expect(unfiltered).toEqual(['runs', 'run_123', 'agent-sessions']);
    expect(operator).toEqual(['runs', 'run_123', 'agent-sessions', 'operator']);
    expect(operator.slice(0, unfiltered.length)).toEqual([...unfiltered]);
  });
});
