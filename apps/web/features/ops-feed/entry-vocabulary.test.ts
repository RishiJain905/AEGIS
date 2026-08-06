import { describe, expect, it } from 'vitest';

import type { RunFeedEntry } from '@/features/command-surface';

import { describeEntry, isRawSummary } from './entry-vocabulary';

function entry(overrides: Partial<RunFeedEntry> & { type: string }): RunFeedEntry {
  return {
    eventId: 'evt_1',
    sequence: 1,
    simTime: '2026-03-04T09:15:00Z',
    category: 'agent',
    initiator: null,
    summary: overrides.type,
    payload: {},
    ...overrides,
  } as RunFeedEntry;
}

describe('isRawSummary', () => {
  it('recognises the API fallback shapes', () => {
    expect(isRawSummary('sim.hidden_condition.revealed')).toBe(true);
    expect(isRawSummary('agent.task.failed (asset:device-analyst-01)')).toBe(true);
  });

  it('leaves real prose alone', () => {
    expect(isRawSummary('WATCHTOWER flagged repeated auth failures')).toBe(false);
    expect(isRawSummary('Alert raised on the analyst workstation.')).toBe(false);
  });
});

describe('describeEntry', () => {
  it('keeps a sentence the backend already wrote', () => {
    expect(
      describeEntry(
        entry({ type: 'agent.task.completed', summary: 'ORACLE ranked three hypotheses' }),
      ),
    ).toBe('ORACLE ranked three hypotheses');
  });

  // The dotted event name is the wire, not the room. It reached the Chronicle verbatim.
  it('names a revealed cause the way the rest of the room names it', () => {
    expect(
      describeEntry(
        entry({
          type: 'sim.hidden_condition.revealed',
          category: 'reveal',
          payload: { conditionId: 'condition-vendor-key-reuse' },
        }),
      ),
    ).toBe('Underlying cause revealed: Vendor key reuse');
  });

  it('says what an agent failure means, with the role that owns it', () => {
    expect(
      describeEntry(
        entry({
          type: 'agent.task.failed',
          summary: 'agent.task.failed (asset:device-analyst-01)',
          payload: { role: 'trace', assetId: 'asset:device-analyst-01' },
        }),
      ),
    ).toBe('TRACE could not finish its task on asset:device-analyst-01');
  });

  it('carries the reason when the failure has one', () => {
    expect(
      describeEntry(
        entry({
          type: 'agent.task.failed',
          payload: { role: 'BASTION', error: 'no incident open on this run' },
        }),
      ),
    ).toBe('BASTION could not finish its task — no incident open on this run');
  });

  it('reads the attributable error fields the backend now emits', () => {
    expect(
      describeEntry(
        entry({
          type: 'agent.task.failed',
          payload: {
            role: 'TRACE',
            errorCode: 'PROVIDER_FAILURE',
            errorMessage: 'Provider request timed out',
          },
        }),
      ),
    ).toBe('TRACE could not finish its task — Provider request timed out (PROVIDER_FAILURE)');
  });

  it('names the role on a run-stop cancellation', () => {
    expect(
      describeEntry(
        entry({
          type: 'agent.task.failed',
          payload: {
            role: 'BASTION',
            errorCode: 'TASK_CANCELLED',
            errorMessage: 'Run stopped while the task was in flight',
          },
        }),
      ),
    ).toBe(
      'BASTION could not finish its task — Run stopped while the task was in flight (TASK_CANCELLED)',
    );
  });

  it('reads a status change as a sentence about the asset', () => {
    expect(
      describeEntry(
        entry({
          type: 'sim.asset.status_changed',
          payload: { assetId: 'asset:db-finance-01', status: 'compromised' },
        }),
      ),
    ).toBe('asset:db-finance-01 is now compromised');
  });

  // A backend event nobody has phrased yet must still be readable, never a dotted id.
  it('degrades an unknown event to a sentence rather than an identifier', () => {
    const said = describeEntry(entry({ type: 'sim.branch.collapsed' }));
    expect(said).toBe('Sim branch collapsed');
    expect(said).not.toContain('.');
  });
});
