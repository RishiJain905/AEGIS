'use client';

import { useRef, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  agentSessionDetailSchema,
  parseContract,
  type AgentSessionDetailV1,
  type AgentTaskV1,
  type AutonomyInitiatorV1,
} from '@aegis/contracts-ts';

import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

/** Roles a player can task from the chat (SCRIBE is available but de-emphasised). */
export const CHAT_ROLES = ['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION'] as const;
export type ChatRole = (typeof CHAT_ROLES)[number];

const _CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/** Generate a `trc_` runtime id (ULID-shaped: 26 Crockford base32 chars). */
export function newTraceId(): string {
  let body = '';
  for (let i = 0; i < 26; i += 1) {
    body += _CROCKFORD.charAt(Math.floor(Math.random() * _CROCKFORD.length));
  }
  return `trc_${body}`;
}

function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`;
}

// Upper bound on how long the UI waits for an inline agent turn before it stops
// blocking the composer. The backend runs the model inline and commits terminal state
// (including failures) before responding, so a request that outlives this is a stuck
// socket, not live work — abort it so the pending state resolves. The committed turn,
// if the backend did finish, still surfaces via the polling refetch of the session list.
export const SEND_TIMEOUT_MS = 180_000;

async function requestJson<T>(
  path: string,
  init: RequestInit,
  parse: (data: unknown) => T,
): Promise<T> {
  const response = await apiFetch(path, { ...init, signal: AbortSignal.timeout(SEND_TIMEOUT_MS) });
  if (!response.ok) {
    let envelope: { code?: string; message?: string; traceId?: string } | undefined;
    try {
      envelope = (await response.json()) as typeof envelope;
    } catch {
      envelope = undefined;
    }
    throw new ApiClientError({
      code: envelope?.code ?? 'HTTP_ERROR',
      message: envelope?.message ?? `Request failed with status ${String(response.status)}`,
      status: response.status,
      traceId: envelope?.traceId,
    });
  }
  return parse((await response.json()) as unknown);
}

/** Task statuses that are still in flight (the turn is not yet resolved). */
const NON_TERMINAL_TASK_STATUSES = new Set(['queued', 'running']);

/** Cadence while the backend still owns a turn somebody is waiting on. */
const WORKING_POLL_MS = 2_500;

/**
 * Cadence for consumers that only read slow-moving background agent state.
 *
 * The hypothesis ledger reads the *unfiltered* session list so it can see the autonomy
 * worker's bias-guard challenges. Those sessions run long — legitimately minutes on the
 * local reasoning model — so sharing the operator turn's 2.5s cadence meant the cockpit
 * held a permanent fast poll for data that changes a few times a run.
 */
const BACKGROUND_POLL_MS = 20_000;

/**
 * How long a task may sit in flight before it stops earning a fast poll.
 *
 * A turn the backend never resolves — a worker that died mid-task, a provider call that
 * dropped — leaves its row `running` forever. Keyed on status alone, one such row pinned
 * the cockpit to a 2.5s poll for the rest of the session, and no reply was ever coming.
 * Matches the client-side turn deadline: past it the panel has already given up on the
 * turn, so polling for its result is pointless.
 */
const IN_FLIGHT_POLL_HORIZON_MS = 600_000;

function isRecentInFlightTask(task: AgentTaskV1, now: number): boolean {
  if (!NON_TERMINAL_TASK_STATUSES.has(task.status)) {
    return false;
  }
  const startedAt = Date.parse(task.startedAt ?? task.createdAt);
  return Number.isNaN(startedAt) || now - startedAt < IN_FLIGHT_POLL_HORIZON_MS;
}

export type AgentSessionsPollCadence = 'operator-turn' | 'background';

/**
 * How often the run's agent sessions should be re-read, or `false` for not at all.
 *
 * Exported so the request budget is pinned by tests rather than inferred from behaviour.
 */
export function agentSessionsPollIntervalMs(
  details: AgentSessionDetailV1[] | undefined,
  cadence: AgentSessionsPollCadence = 'operator-turn',
  now: number = Date.now(),
): number | false {
  const working = (details ?? []).some((detail) =>
    detail.tasks.some((task) => isRecentInFlightTask(task, now)),
  );
  if (!working) {
    return false;
  }
  return cadence === 'background' ? BACKGROUND_POLL_MS : WORKING_POLL_MS;
}

/**
 * Fetch the agent sessions anchored to a run (restores the chat threads).
 *
 * Pass `origin: 'operator'` for anything showing the operator's own conversations —
 * otherwise the autonomy worker's background triage threads (WATCHTOWER sweeps,
 * bias-guard checks) come back too, and the operator sees sessions they never started
 * plus a permanent "Working…" from tasks that aren't theirs. Consumers that genuinely
 * want autonomous activity (the hypothesis ledger's bias-guard findings) omit it.
 *
 * `options.enabled` lets an observer stand the query down entirely (the guided walkthrough
 * only watches agent activity while a beat is waiting on it). Defaults to on, so existing
 * callers are unaffected.
 */
export function useRunAgentSessions(
  runId: string,
  origin?: AutonomyInitiatorV1,
  options?: { enabled?: boolean; cadence?: 'operator-turn' | 'background' },
) {
  return useQuery({
    queryKey: queryKeys.agentSessions.listForRun(runId, origin),
    enabled: Boolean(runId) && (options?.enabled ?? true),
    queryFn: async ({ signal }): Promise<AgentSessionDetailV1[]> => {
      const query = origin ? `?origin=${origin}` : '';
      const response = await apiFetch(`/api/v1/runs/${runId}/agent-sessions${query}`, { signal });
      if (!response.ok) {
        throw new ApiClientError({
          code: 'HTTP_ERROR',
          message: `Failed to load agent sessions (status ${String(response.status)})`,
          status: response.status,
        });
      }
      const body = (await response.json()) as { sessions?: unknown[] };
      const raw = Array.isArray(body.sessions) ? body.sessions : [];
      return raw.map((entry) => parseContract(agentSessionDetailSchema, entry));
    },
    // Poll while a task is still queued/running so a turn that reaches a terminal state on
    // the backend surfaces here even if the originating request is slow or a realtime
    // invalidation was missed. Idle threads do not poll at all — the provider's `agent.*`
    // handler invalidates this key, so the poll is a backstop, not the delivery mechanism.
    refetchInterval: (query) => agentSessionsPollIntervalMs(query.state.data, options?.cadence),
  });
}

export interface SendMessageInput {
  role: ChatRole;
  instructions: string;
  /** Existing run-scoped session for this role, if the thread already started. */
  sessionId?: string;
}

const TERMINAL_FAILURE_STATUSES = new Set(['failed', 'timed_out']);

/**
 * Read the terminal task status out of an interactive agent response so the caller can decide
 * whether to auto-retry. The task-create route returns the completed `AgentTaskV1` (has
 * `status`); the session-create route returns the session detail, whose newest task carries
 * the status. Returns null when no status can be read (treated as non-failure).
 */
export function terminalTaskStatus(data: unknown): string | null {
  if (typeof data !== 'object' || data === null) {
    return null;
  }
  const record = data as Record<string, unknown>;
  // Task-create response shape: the task itself.
  if (typeof record.status === 'string') {
    return record.status;
  }
  // Session-create response shape: AgentSessionDetailV1 with a tasks array.
  const tasks = record.tasks;
  if (Array.isArray(tasks) && tasks.length > 0) {
    const newest = tasks[tasks.length - 1] as { status?: unknown };
    return typeof newest.status === 'string' ? newest.status : null;
  }
  return null;
}

function isTaskFailure(status: string | null): boolean {
  return status !== null && TERMINAL_FAILURE_STATUSES.has(status);
}

/**
 * Send an operator message: create a new run-scoped session for the role on the
 * first turn, or enqueue a follow-up task on the existing session. Both calls run
 * the agent inline server-side and return the finished turn, so on success we
 * refetch the run's sessions to render the result.
 */
export function useSendAgentMessage(runId: string) {
  const queryClient = useQueryClient();
  // Retry state is tracked *per role*, not globally: two roles can legitimately have
  // turns in flight at once, and a single shared flag made one role's automatic retry
  // relabel whichever role the operator happened to be looking at (BUG-023).
  const [retryingRoles, setRetryingRoles] = useState<readonly ChatRole[]>([]);
  const setRetryingRef = useRef(setRetryingRoles);
  setRetryingRef.current = setRetryingRoles;

  const markRetrying = (role: ChatRole, on: boolean) => {
    setRetryingRef.current((prev) => {
      const has = prev.includes(role);
      if (has === on) {
        return prev;
      }
      return on ? [...prev, role] : prev.filter((candidate) => candidate !== role);
    });
  };

  const sendOnce = async ({
    role,
    instructions,
    sessionId,
  }: SendMessageInput): Promise<unknown> => {
    if (sessionId) {
      return requestJson(
        `/api/v1/agent-sessions/${sessionId}/tasks`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            schemaVersion: 1,
            idempotencyKey: newIdempotencyKey('chat'),
            providerId: null,
            instructions,
          }),
        },
        (data) => data,
      );
    }
    return requestJson(
      `/api/v1/runs/${runId}/agent-sessions`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schemaVersion: 1,
          role,
          traceId: newTraceId(),
          enqueueInitialTask: true,
          providerId: null,
          instructions,
        }),
      },
      (data) => data,
    );
  };

  const mutation = useMutation({
    mutationFn: async (input: SendMessageInput): Promise<void> => {
      // Local model tasks can fail transiently; give exactly one automatic retry with a
      // visible "retrying…" state. A second failure is left honest in the thread — no further
      // retries, no swallowing. The retry re-sends on the same session (a fresh task), so the
      // prior failed turn stays visible for the audit trail.
      const first = await sendOnce(input);
      if (!isTaskFailure(terminalTaskStatus(first))) {
        return;
      }
      markRetrying(input.role, true);
      try {
        await sendOnce(input);
      } finally {
        markRetrying(input.role, false);
      }
    },
    onSettled: (_data, _error, variables) => {
      markRetrying(variables.role, false);
    },
    onSuccess: async (_result, variables) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.agentSessions.listForRun(runId),
      });
      if (variables.sessionId) {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.agentSessions.detail(variables.sessionId),
        });
      }
    },
  });

  return Object.assign(mutation, {
    /** Roles whose single automatic re-attempt is currently running. */
    retryingRoles,
    /** Any role retrying at all — kept for callers that do not care which. */
    isRetrying: retryingRoles.length > 0,
  });
}
