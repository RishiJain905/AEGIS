import { describe, expect, it } from 'vitest';

import type { RunFeedEntry } from '@/features/command-surface';

import {
  buildFeedRows,
  isBiasCheck,
  isDetection,
  isNoChangeAutonomyReport,
  latestDetection,
} from './feed-model';

function entry(overrides: Partial<RunFeedEntry> & { sequence: number }): RunFeedEntry {
  return {
    schemaVersion: 1,
    eventId: `evt-${String(overrides.sequence)}`,
    type: 'agent.task.completed',
    category: 'agent',
    simTime: '2026-07-22T00:00:00.000Z',
    initiator: null,
    summary: 'summary',
    payload: {},
    ...overrides,
  };
}

describe('feed-model', () => {
  it('orders rows newest-first by sequence', () => {
    const rows = buildFeedRows([
      entry({ sequence: 1, category: 'alert', initiator: null }),
      entry({ sequence: 3, category: 'incident', initiator: null }),
      entry({ sequence: 2, category: 'proposal', initiator: null }),
    ]);
    const sequences = rows.map((r) => (r.kind === 'entry' ? r.entry.sequence : -1));
    expect(sequences).toEqual([3, 2, 1]);
  });

  it('collapses consecutive no-change autonomy reports into one row', () => {
    const rows = buildFeedRows([
      entry({ sequence: 1, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
      entry({ sequence: 2, initiator: 'autonomy', payload: { noChange: true } }),
      entry({ sequence: 3, initiator: 'autonomy', payload: { status: 'unchanged' } }),
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: 'collapsed', count: 3 });
  });

  it('keeps a lone no-change report as a normal entry (not collapsed)', () => {
    const rows = buildFeedRows([
      entry({ sequence: 1, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.kind).toBe('entry');
  });

  it('does not collapse across a substantive entry', () => {
    const rows = buildFeedRows([
      entry({ sequence: 1, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
      entry({ sequence: 2, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
      entry({
        sequence: 3,
        category: 'proposal',
        initiator: 'autonomy',
        summary: 'Drafted isolation',
      }),
      entry({ sequence: 4, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
      entry({ sequence: 5, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
    ]);
    // Newest-first: [collapsed(5,4)], [entry 3], [collapsed(2,1)]
    expect(rows.map((r) => r.kind)).toEqual(['collapsed', 'entry', 'collapsed']);
  });

  it('never collapses or mutes a reveal detection', () => {
    const reveal = entry({
      sequence: 2,
      category: 'reveal',
      type: 'sim.hidden_condition.revealed',
      initiator: 'autonomy',
      payload: { outcome: 'no_change' },
    });
    expect(isNoChangeAutonomyReport(reveal)).toBe(false);
    expect(isDetection(reveal)).toBe(true);
    const rows = buildFeedRows([
      entry({ sequence: 1, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
      reveal,
    ]);
    const detectionRow = rows.find((r) => r.kind === 'entry' && r.detection);
    expect(detectionRow).toBeDefined();
  });

  it('does not treat an operator-tasked finding as a collapsible no-change report', () => {
    const tasked = entry({ sequence: 1, initiator: 'operator', payload: { outcome: 'no_change' } });
    expect(isNoChangeAutonomyReport(tasked)).toBe(false);
  });

  it('folds one command order into a single row carrying its older events as a trail', () => {
    const rows = buildFeedRows([
      entry({
        sequence: 5,
        category: 'operator_action',
        type: 'operator.action.proposed',
        payload: { proposalId: 'prp_1', scenarioCommand: 'isolate' },
      }),
      entry({
        sequence: 6,
        category: 'execution',
        type: 'action.executed',
        payload: { proposalId: 'prp_1' },
      }),
      entry({
        sequence: 7,
        category: 'operator_action',
        type: 'operator.action.proposed',
        payload: { proposalId: 'prp_2', scenarioCommand: 'observe' },
      }),
    ]);
    expect(rows).toHaveLength(2);
    // Newest-first: the observe order, then the isolate order folded down to its execution.
    const [observed, executed] = rows;
    if (observed?.kind !== 'entry' || executed?.kind !== 'entry') {
      throw new Error('expected two entry rows');
    }
    expect(observed.entry.sequence).toBe(7);
    expect(observed.trail).toEqual([]);
    // The newest event of the order is what renders; the older one rides along.
    expect(executed.entry.sequence).toBe(6);
    expect(executed.trail.map((item) => item.sequence)).toEqual([5]);
  });

  it('leaves entries without a proposal — and non-command traffic — unfolded', () => {
    const rows = buildFeedRows([
      entry({ sequence: 1, category: 'alert', payload: { proposalId: 'prp_1' } }),
      entry({ sequence: 2, category: 'alert', payload: { proposalId: 'prp_1' } }),
      entry({ sequence: 3, category: 'execution', type: 'action.executed', payload: {} }),
    ]);
    expect(rows).toHaveLength(3);
  });

  it('latestDetection returns the highest-sequence reveal', () => {
    const latest = latestDetection([
      entry({ sequence: 1, category: 'reveal', type: 'reveal.asset' }),
      entry({ sequence: 5, category: 'reveal', type: 'reveal.asset' }),
      entry({ sequence: 3, category: 'alert' }),
    ]);
    expect(latest?.sequence).toBe(5);
  });

  it('flags an autonomous bias-guard finding as a bias check', () => {
    const biasCheck = entry({
      sequence: 1,
      initiator: 'autonomy',
      summary: 'ORACLE bias guard: new evidence contradicts the leading hypothesis',
    });
    expect(isBiasCheck(biasCheck)).toBe(true);
    const rows = buildFeedRows([biasCheck]);
    expect(rows[0]).toMatchObject({ kind: 'entry', biasCheck: true });
  });

  it('does not flag an operator-tasked or non-bias finding as a bias check', () => {
    expect(
      isBiasCheck(entry({ sequence: 1, initiator: 'operator', summary: 'bias guard note' })),
    ).toBe(false);
    expect(
      isBiasCheck(entry({ sequence: 2, initiator: 'autonomy', summary: 'routine sweep' })),
    ).toBe(false);
  });
});
