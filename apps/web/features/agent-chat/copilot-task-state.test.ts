import type { AgentTaskV1 } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import {
  CLIENT_DEADLINE_ERROR_CODE,
  COPILOT_TASK_DEADLINE_MS,
  EMPTY_ROLE_TASK_STATE,
  copilotTaskReducer,
  deriveRoleTurn,
  initialCopilotTaskMap,
  latestSessionForRole,
  otherBusyRoles,
  type RoleTaskState,
  type RoleTurnView,
} from './copilot-task-state';
import { CHAT_ROLES, SEND_TIMEOUT_MS, type ChatRole } from './use-agent-chat';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function task(overrides: Partial<AgentTaskV1> = {}): AgentTaskV1 {
  return {
    schemaVersion: 1,
    id: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    sessionId: 'agent-session:ags_1',
    runId: RUN_ID,
    incidentId: null,
    status: 'running',
    attempt: 1,
    idempotencyKey: 'chat-1',
    traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    providerId: 'openai-compatible',
    instructions: 'Trace the unseen-source alerts',
    initiator: 'operator',
    errorCode: null,
    errorMessage: null,
    createdAt: '2026-07-30T00:00:00.000Z',
    updatedAt: '2026-07-30T00:00:00.000Z',
    startedAt: null,
    completedAt: null,
    ...overrides,
  } as AgentTaskV1;
}

function local(overrides: Partial<RoleTaskState> = {}): RoleTaskState {
  return { ...EMPTY_ROLE_TASK_STATE, ...overrides };
}

describe('copilot deadline constant', () => {
  it('stays well above the per-request abort so it never resolves live work', () => {
    // The fetch abort ends one HTTP request; the backend task usually keeps running.
    // A deadline at or below it would declare live turns dead.
    expect(COPILOT_TASK_DEADLINE_MS).toBeGreaterThan(SEND_TIMEOUT_MS);
    expect(COPILOT_TASK_DEADLINE_MS).toBeGreaterThanOrEqual(600_000);
  });
});

describe('copilotTaskReducer', () => {
  it('scopes a submission to one role and leaves the others untouched', () => {
    const next = copilotTaskReducer(initialCopilotTaskMap, {
      type: 'submitted',
      role: 'TRACE',
      instructions: 'Trace it',
      atMs: 1000,
    });
    expect(next.TRACE.sending).toBe(true);
    expect(next.TRACE.instructions).toBe('Trace it');
    for (const role of CHAT_ROLES.filter((candidate) => candidate !== 'TRACE')) {
      expect(next[role]).toBe(initialCopilotTaskMap[role]);
    }
  });

  it('treats a repeated deadline for the same turn as a no-op', () => {
    const first = copilotTaskReducer(initialCopilotTaskMap, {
      type: 'deadline-reached',
      role: 'ORACLE',
      turnKey: 'atk_1',
    });
    const second = copilotTaskReducer(first, {
      type: 'deadline-reached',
      role: 'ORACLE',
      turnKey: 'atk_1',
    });
    // Identity, not just equality: a changed object would re-run the panel's effect.
    expect(second).toBe(first);
  });

  it('treats a repeated settle as a no-op', () => {
    const settled = copilotTaskReducer(initialCopilotTaskMap, {
      type: 'send-settled',
      role: 'WATCHTOWER',
    });
    expect(settled).toBe(initialCopilotTaskMap);
  });

  it('clears the previous turn error and deadline when the role submits again', () => {
    let state = copilotTaskReducer(initialCopilotTaskMap, {
      type: 'send-failed',
      role: 'TRACE',
      error: { code: 'PROVIDER_FAILURE', message: 'boom', traceId: null },
    });
    state = copilotTaskReducer(state, {
      type: 'deadline-reached',
      role: 'TRACE',
      turnKey: 'atk_old',
    });
    state = copilotTaskReducer(state, {
      type: 'submitted',
      role: 'TRACE',
      instructions: 'Trace it again',
      atMs: 2000,
    });
    expect(state.TRACE.error).toBeNull();
    expect(state.TRACE.deadlinedTurnKey).toBeNull();
  });
});

describe('deriveRoleTurn', () => {
  it('is idempotent for a repeated terminal task: same view, never busy', () => {
    const failed = task({ status: 'failed', errorCode: 'PROVIDER_FAILURE', errorMessage: 'boom' });
    const first = deriveRoleTurn('TRACE', failed, local());
    // The exact same authoritative row applied a second time (a duplicate
    // agent.task.failed event, or a poll refetch returning the same row).
    const second = deriveRoleTurn('TRACE', failed, local());
    expect(second).toStrictEqual(first);
    expect(first.phase).toBe('failed');
    expect(first.busy).toBe(false);
    expect(first.errorCode).toBe('PROVIDER_FAILURE');
    expect(first.errorMessage).toBe('boom');
    expect(first.taskId).toBe(failed.id);
    expect(first.traceId).toBe(failed.traceId);
    expect(first.retryInstructions).toBe('Trace the unseen-source alerts');
  });

  it('resolves every terminal status, not just failed', () => {
    expect(deriveRoleTurn('TRACE', task({ status: 'completed' }), local()).phase).toBe('succeeded');
    expect(deriveRoleTurn('TRACE', task({ status: 'cancelled' }), local()).phase).toBe('cancelled');
    expect(deriveRoleTurn('TRACE', task({ status: 'timed_out' }), local()).phase).toBe('timed_out');
    for (const status of ['completed', 'cancelled', 'timed_out', 'failed'] as const) {
      expect(deriveRoleTurn('TRACE', task({ status }), local()).busy).toBe(false);
    }
  });

  it('keeps a role busy while its own POST is in flight and no task row exists yet', () => {
    const view = deriveRoleTurn(
      'TRACE',
      undefined,
      local({ sending: true, instructions: 'Trace it', submittedAtMs: 1000 }),
    );
    expect(view.phase).toBe('sending');
    expect(view.busy).toBe(true);
    expect(view.turnKey).toBe('local:1000');
  });

  it('lets a fresh send outrank the previous turn terminal status', () => {
    const view = deriveRoleTurn(
      'TRACE',
      task({ status: 'completed' }),
      local({ sending: true, instructions: 'Again', submittedAtMs: 5000 }),
    );
    expect(view.phase).toBe('sending');
  });

  it('lets a live backend task outrank a stale transport error', () => {
    // The 3-minute fetch abort fires while the backend turn is still legitimately
    // running. The card must stay working, not flip to a bogus failure.
    const view = deriveRoleTurn(
      'TRACE',
      task({ status: 'running' }),
      local({ error: { code: 'REQUEST_TIMEOUT', message: 'signal timed out', traceId: null } }),
    );
    expect(view.phase).toBe('working');
    expect(view.busy).toBe(true);
    expect(view.errorMessage).toBeNull();
  });

  it('surfaces a transport error that never produced a task row', () => {
    const view = deriveRoleTurn(
      'TRACE',
      undefined,
      local({
        instructions: 'Trace it',
        submittedAtMs: 10,
        error: { code: 'HTTP_ERROR', message: 'Request failed with status 500', traceId: 'trc_9' },
      }),
    );
    expect(view.phase).toBe('failed');
    expect(view.busy).toBe(false);
    expect(view.errorCode).toBe('HTTP_ERROR');
    expect(view.traceId).toBe('trc_9');
    expect(view.retryInstructions).toBe('Trace it');
  });

  it('resolves a stuck running task once the client deadline fires for that turn', () => {
    const running = task({ status: 'running' });
    const view = deriveRoleTurn(
      'TRACE',
      running,
      local({ deadlinedTurnKey: running.id, instructions: 'Trace it' }),
    );
    expect(view.phase).toBe('timed_out');
    expect(view.busy).toBe(false);
    expect(view.errorCode).toBe(CLIENT_DEADLINE_ERROR_CODE);
    expect(view.retryInstructions).toBe('Trace the unseen-source alerts');
  });

  it('does not apply a deadline recorded against a different turn', () => {
    const running = task({ id: 'atk_new', status: 'running' });
    const view = deriveRoleTurn(
      'TRACE',
      running,
      local({ deadlinedTurnKey: 'atk_old', instructions: 'Trace it' }),
    );
    expect(view.phase).toBe('working');
    expect(view.busy).toBe(true);
  });

  it('lets an authoritative terminal status beat a deadline that already fired', () => {
    const failed = task({ status: 'failed', errorCode: 'PROVIDER_FAILURE', errorMessage: 'boom' });
    const view = deriveRoleTurn('TRACE', failed, local({ deadlinedTurnKey: failed.id }));
    expect(view.phase).toBe('failed');
    expect(view.errorCode).toBe('PROVIDER_FAILURE');
  });

  it('starts the deadline clock from the task row so a reload does not reset it', () => {
    const running = task({ status: 'running', createdAt: '2026-07-30T00:00:00.000Z' });
    const view = deriveRoleTurn('TRACE', running, local({ submittedAtMs: 999 }));
    expect(view.startedAtMs).toBe(Date.parse('2026-07-30T00:00:00.000Z'));
  });
});

describe('per-role isolation', () => {
  it('reports the roles that own an in-flight turn, excluding the selected one', () => {
    const views = Object.fromEntries(
      CHAT_ROLES.map((role) => [
        role,
        deriveRoleTurn(
          role,
          role === 'TRACE' || role === 'WATCHTOWER' ? task({ status: 'running' }) : undefined,
          local(),
        ),
      ]),
    ) as Record<ChatRole, RoleTurnView>;
    expect(otherBusyRoles(views, 'ORACLE')).toStrictEqual(['WATCHTOWER', 'TRACE']);
    expect(otherBusyRoles(views, 'TRACE')).toStrictEqual(['WATCHTOWER']);
  });

  it('selects the newest session belonging to the requested role only', () => {
    const detail = (id: string, role: string) =>
      ({
        session: { id, role },
        tasks: [],
      }) as never;
    const details = [detail('a', 'WATCHTOWER'), detail('b', 'TRACE'), detail('c', 'TRACE')];
    expect(latestSessionForRole(details, 'TRACE')?.session.id).toBe('c');
    expect(latestSessionForRole(details, 'ORACLE')).toBeUndefined();
  });
});
