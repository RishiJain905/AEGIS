import { describe, expect, it } from 'vitest';

import { getReplayDiffFixture, getReplayStateFixture } from '@/fixtures/replay-fixture';

describe('replay fixture reconstruction projections', () => {
  it('reconstructs later domains as the cursor advances', () => {
    const early = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 40 });
    const late = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    expect(early.incidents).toHaveLength(0);
    expect(late.incidents.length).toBeGreaterThan(0);
    expect(late.proposals.length).toBeGreaterThan(0);
    expect(late.approvals.length).toBeGreaterThan(0);
    expect(late.reports.length).toBeGreaterThan(0);
    expect(late.auditEvents.length).toBeGreaterThan(early.auditEvents.length);
  });

  it('produces meaningful diffs between cursors', () => {
    const diff = getReplayDiffFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', 100, 500);
    expect(diff.equivalent).toBe(false);
    expect(diff.entries.length).toBeGreaterThan(0);
  });

  it('fails closed for unavailable or corrupt replay data', () => {
    expect(() => getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FZ0')).toThrow();
    expect(() => getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FZ1')).toThrow();
    expect(() => getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FZ2')).toThrow();
  });
});
