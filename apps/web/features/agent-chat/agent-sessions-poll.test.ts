/**
 * Request budget for the run's agent-session reads.
 *
 * QA counted 28 `/agent-sessions` requests against one idle run in 60 seconds — a steady
 * ~2s cadence with nothing working. Two things kept the fast poll alive: the hypothesis
 * ledger reads the *unfiltered* session list so it can see the autonomy worker's bias-guard
 * challenges, and those sweeps are in flight for minutes; and a task the backend never
 * resolves stays `running` forever, so status alone can pin the poll open for the rest of
 * the session.
 */

import type { AgentSessionDetailV1, AgentTaskV1 } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { agentSessionsPollIntervalMs } from './use-agent-chat';

const NOW = Date.parse('2026-08-02T12:00:00.000Z');

function task(overrides: Partial<AgentTaskV1> = {}): AgentTaskV1 {
  return {
    schemaVersion: 1,
    id: 'task_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    sessionId: 'agsess_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    incidentId: null,
    status: 'running',
    attempt: 1,
    idempotencyKey: 'idem-1',
    traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    providerId: 'mock',
    initiator: 'operator',
    createdAt: '2026-08-02T11:59:50.000Z',
    updatedAt: '2026-08-02T11:59:50.000Z',
    startedAt: '2026-08-02T11:59:50.000Z',
    completedAt: null,
    ...overrides,
  } as AgentTaskV1;
}

function sessions(...tasks: AgentTaskV1[]): AgentSessionDetailV1[] {
  return [
    {
      session: { role: 'ORACLE' },
      tasks,
      artifacts: [],
    } as unknown as AgentSessionDetailV1,
  ];
}

describe('agentSessionsPollIntervalMs', () => {
  it('does not poll when nothing is in flight', () => {
    expect(
      agentSessionsPollIntervalMs(sessions(task({ status: 'completed' })), 'operator-turn', NOW),
    ).toBe(false);
    expect(agentSessionsPollIntervalMs(undefined, 'operator-turn', NOW)).toBe(false);
    expect(agentSessionsPollIntervalMs([], 'operator-turn', NOW)).toBe(false);
  });

  it('polls fast while the operator is waiting on a turn', () => {
    expect(agentSessionsPollIntervalMs(sessions(task()), 'operator-turn', NOW)).toBe(2_500);
  });

  it('polls lazily for consumers reading background autonomy state', () => {
    // Same in-flight task, different consumer: the hypothesis ledger is not waiting on it.
    expect(agentSessionsPollIntervalMs(sessions(task()), 'background', NOW)).toBe(20_000);
  });

  it('stops fast-polling a task the backend never resolved', () => {
    const stranded = task({
      startedAt: '2026-08-02T11:30:00.000Z',
      createdAt: '2026-08-02T11:30:00.000Z',
    });
    expect(agentSessionsPollIntervalMs(sessions(stranded), 'operator-turn', NOW)).toBe(false);
  });

  it('still polls a long-but-live turn inside the deadline', () => {
    // The local reasoning model legitimately takes minutes; only past the client's own turn
    // deadline does a task stop earning a poll.
    const slow = task({
      startedAt: '2026-08-02T11:52:00.000Z',
      createdAt: '2026-08-02T11:52:00.000Z',
    });
    expect(agentSessionsPollIntervalMs(sessions(slow), 'operator-turn', NOW)).toBe(2_500);
  });

  it('falls back to createdAt when a queued task has not started', () => {
    const queued = task({ status: 'queued', startedAt: null });
    expect(agentSessionsPollIntervalMs(sessions(queued), 'operator-turn', NOW)).toBe(2_500);
  });
});
