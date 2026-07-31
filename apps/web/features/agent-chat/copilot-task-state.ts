import type { AgentSessionDetailV1, AgentTaskV1 } from '@aegis/contracts-ts';

import { CHAT_ROLES, type ChatRole } from './use-agent-chat';

/**
 * Per-role copilot turn state.
 *
 * Two rules drive everything in this module:
 *
 * 1. **Identity is per role.** Every role owns its own in-flight turn, its own busy
 *    state and its own history. Selecting a different role changes the *view* only —
 *    it never renames, re-owns or cancels another role's task (BUG-023).
 * 2. **The backend task row is authoritative.** Busy/failed/succeeded are *derived*
 *    from the persisted `AgentTaskV1.status`, never stored. Deriving is a pure
 *    function of (task, local state), so applying the same terminal transition twice
 *    is a no-op by construction, and a terminal transition that arrives for a role
 *    the operator is not currently looking at still resolves that role (BUG-024).
 *
 * The client keeps only what the backend cannot tell it: whether a POST is still in
 * flight, the transport error if one failed, and whether the client-side safety
 * deadline has fired for the turn.
 */

/** Statuses meaning the backend still owns the turn. */
const IN_FLIGHT_TASK_STATUSES: ReadonlySet<string> = new Set(['queued', 'running']);

/** Statuses meaning the backend has finished with the turn, one way or another. */
const TERMINAL_TASK_STATUSES: ReadonlySet<string> = new Set([
  'completed',
  'failed',
  'cancelled',
  'timed_out',
]);

export function isInFlightTaskStatus(status: string): boolean {
  return IN_FLIGHT_TASK_STATUSES.has(status);
}

export function isTerminalTaskStatus(status: string): boolean {
  return TERMINAL_TASK_STATUSES.has(status);
}

/**
 * How long the client waits for *any* terminal transition before it resolves the card
 * itself rather than spinning forever.
 *
 * Deliberately generous: the local reasoning model legitimately takes minutes per turn,
 * and this bound has to sit well above `SEND_TIMEOUT_MS` (the per-request fetch abort).
 * When the fetch aborts at 3 minutes the *task* usually keeps running server-side, so
 * the turn stays owned by the backend and only this deadline can end it. The relationship
 * (deadline > SEND_TIMEOUT_MS) is asserted in copilot-task-state.test.ts.
 */
export const COPILOT_TASK_DEADLINE_MS = 600_000;

/** How often the panel re-checks the deadline for busy roles. */
export const DEADLINE_POLL_MS = 15_000;

/** Error code synthesised when the client deadline — not the backend — ends a turn. */
export const CLIENT_DEADLINE_ERROR_CODE = 'CLIENT_TASK_DEADLINE';

export type CopilotPhase =
  /** Nothing in flight for this role. */
  | 'idle'
  /** The operator's POST is in flight and no task row has surfaced yet. */
  | 'sending'
  /** An authoritative task row for this role is queued/running. */
  | 'working'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'timed_out';

export interface CopilotClientError {
  code: string | null;
  message: string;
  traceId: string | null;
}

/** The only mutable copilot state the client owns, per role. */
export interface RoleTaskState {
  /** Prompt this role last submitted — the retry source when no task row exists yet. */
  instructions: string | null;
  /** Wall clock of the local submit; the deadline anchor until a task row appears. */
  submittedAtMs: number | null;
  /** A POST for this role is in flight. */
  sending: boolean;
  /** Transport/HTTP failure from this role's own submission (not a backend task failure). */
  error: CopilotClientError | null;
  /** Turn key the client deadline fired against, so a *new* turn is not born timed out. */
  deadlinedTurnKey: string | null;
}

export const EMPTY_ROLE_TASK_STATE: RoleTaskState = {
  instructions: null,
  submittedAtMs: null,
  sending: false,
  error: null,
  deadlinedTurnKey: null,
};

export type CopilotTaskMap = Readonly<Record<ChatRole, RoleTaskState>>;

export const initialCopilotTaskMap: CopilotTaskMap = Object.fromEntries(
  CHAT_ROLES.map((role) => [role, EMPTY_ROLE_TASK_STATE]),
) as CopilotTaskMap;

export type CopilotTaskAction =
  | { type: 'submitted'; role: ChatRole; instructions: string; atMs: number }
  | { type: 'send-failed'; role: ChatRole; error: CopilotClientError }
  | { type: 'send-settled'; role: ChatRole }
  | { type: 'deadline-reached'; role: ChatRole; turnKey: string };

function replaceRole(state: CopilotTaskMap, role: ChatRole, next: RoleTaskState): CopilotTaskMap {
  return { ...state, [role]: next };
}

/**
 * Reduce a copilot action onto the per-role map.
 *
 * Every branch returns the *identical* state object when nothing changed, so repeated
 * identical actions (a duplicate deadline tick, a duplicate settle) are true no-ops and
 * cannot drive a render loop.
 */
export function copilotTaskReducer(
  state: CopilotTaskMap,
  action: CopilotTaskAction,
): CopilotTaskMap {
  const current = state[action.role];
  switch (action.type) {
    case 'submitted':
      // A new turn clears the previous turn's transport error and deadline for this role
      // only — other roles are untouched.
      return replaceRole(state, action.role, {
        instructions: action.instructions,
        submittedAtMs: action.atMs,
        sending: true,
        error: null,
        deadlinedTurnKey: null,
      });
    case 'send-failed':
      return replaceRole(state, action.role, { ...current, error: action.error });
    case 'send-settled':
      if (!current.sending) {
        return state;
      }
      return replaceRole(state, action.role, { ...current, sending: false });
    case 'deadline-reached':
      if (current.deadlinedTurnKey === action.turnKey) {
        return state;
      }
      return replaceRole(state, action.role, { ...current, deadlinedTurnKey: action.turnKey });
    default:
      return state;
  }
}

/** Newest operator session for a role (the active thread), if any. */
export function latestSessionForRole(
  details: readonly AgentSessionDetailV1[] | undefined,
  role: ChatRole,
): AgentSessionDetailV1 | undefined {
  const forRole = (details ?? []).filter((detail) => detail.session.role === role);
  return forRole.length > 0 ? forRole[forRole.length - 1] : undefined;
}

/** Newest task on a session detail — the turn that owns the role right now. */
export function latestTaskOf(detail: AgentSessionDetailV1 | undefined): AgentTaskV1 | undefined {
  if (!detail || detail.tasks.length === 0) {
    return undefined;
  }
  return detail.tasks[detail.tasks.length - 1];
}

export interface RoleTurnView {
  role: ChatRole;
  phase: CopilotPhase;
  /** True while this role's composer must stay disabled. */
  busy: boolean;
  /** Stable identity of the turn this role owns (task id, or the local submit). */
  turnKey: string | null;
  /** Backend task id, once one exists. Surfaced in the failure card. */
  taskId: string | null;
  /** Trace/request id for support, from the task row or the transport error. */
  traceId: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  /** Prompt a Retry action should re-send as a NEW task, or null if nothing to retry. */
  retryInstructions: string | null;
  /** When the current turn started, for the client deadline. */
  startedAtMs: number | null;
}

function parseStartedAt(task: AgentTaskV1 | undefined): number | null {
  if (!task) {
    return null;
  }
  const parsed = Date.parse(task.startedAt ?? task.createdAt);
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * Derive one role's rendered turn state from the authoritative task plus local state.
 *
 * Precedence, highest first:
 *  1. an in-flight backend task — the backend owns the turn, so a stale transport
 *     error (a 3-minute fetch abort against a turn that is still running) must not
 *     strand or falsely resolve the card;
 *  2. a POST still in flight, which outranks the *previous* turn's terminal status;
 *  3. the client deadline, which only ever applies to the turn it fired against;
 *  4. the authoritative terminal status;
 *  5. a transport error with no task row to speak for it.
 */
export function deriveRoleTurn(
  role: ChatRole,
  task: AgentTaskV1 | undefined,
  local: RoleTaskState,
): RoleTurnView {
  const turnKey =
    task?.id ?? (local.submittedAtMs === null ? null : `local:${String(local.submittedAtMs)}`);
  const backendInFlight = task !== undefined && isInFlightTaskStatus(task.status);
  const backendTerminal = task !== undefined && isTerminalTaskStatus(task.status);
  const deadlined = turnKey !== null && local.deadlinedTurnKey === turnKey;

  let phase: CopilotPhase;
  if (backendInFlight && !deadlined) {
    phase = 'working';
  } else if (local.sending) {
    phase = 'sending';
  } else if (backendTerminal) {
    phase = task.status === 'completed' ? 'succeeded' : (task.status as CopilotPhase);
  } else if (deadlined) {
    phase = 'timed_out';
  } else if (local.error !== null) {
    phase = 'failed';
  } else {
    phase = 'idle';
  }

  const busy = phase === 'sending' || phase === 'working';

  let errorCode: string | null = null;
  let errorMessage: string | null = null;
  let traceId: string | null = task?.traceId ?? null;
  if (phase === 'timed_out' && !backendTerminal) {
    errorCode = CLIENT_DEADLINE_ERROR_CODE;
    errorMessage = `No result after ${String(
      Math.round(COPILOT_TASK_DEADLINE_MS / 60_000),
    )} minutes. The task never reported a terminal state.`;
  } else if (backendTerminal && phase !== 'succeeded' && phase !== 'sending') {
    errorCode = task.errorCode ?? null;
    errorMessage = task.errorMessage ?? null;
  } else if (phase === 'failed' && local.error !== null) {
    errorCode = local.error.code;
    errorMessage = local.error.message;
    traceId = local.error.traceId ?? traceId;
  }

  return {
    role,
    phase,
    busy,
    turnKey,
    taskId: task?.id ?? null,
    traceId,
    errorCode,
    errorMessage,
    retryInstructions: busy ? null : (task?.instructions ?? local.instructions),
    startedAtMs: parseStartedAt(task) ?? local.submittedAtMs,
  };
}

/** Roles other than `selected` that currently own an in-flight turn. */
export function otherBusyRoles(
  views: Readonly<Record<ChatRole, RoleTurnView>>,
  selected: ChatRole,
): ChatRole[] {
  return CHAT_ROLES.filter((role) => role !== selected && views[role].busy);
}
