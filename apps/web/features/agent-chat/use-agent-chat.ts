'use client';

import { useRef, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  agentSessionDetailSchema,
  parseContract,
  type AgentSessionDetailV1,
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
const SEND_TIMEOUT_MS = 180_000;

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

function hasInFlightTask(details: AgentSessionDetailV1[] | undefined): boolean {
  return (details ?? []).some((detail) =>
    detail.tasks.some((task) => NON_TERMINAL_TASK_STATUSES.has(task.status)),
  );
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
  options?: { enabled?: boolean },
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
    // Poll while any task is still queued/running so a turn that reaches a terminal
    // state on the backend surfaces here even if the originating request is slow or a
    // realtime invalidation was missed. Idle threads do not poll.
    refetchInterval: (query) => (hasInFlightTask(query.state.data) ? 2500 : false),
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
  // Surfaced so the thread can show a single, honest "retrying…" state during the one
  // automatic re-attempt. A ref backs the state so the mutationFn reads a stable setter.
  const [isRetrying, setIsRetrying] = useState(false);
  const retryingRef = useRef(setIsRetrying);
  retryingRef.current = setIsRetrying;

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
      retryingRef.current(true);
      try {
        await sendOnce(input);
      } finally {
        retryingRef.current(false);
      }
    },
    onSettled: () => {
      retryingRef.current(false);
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

  return Object.assign(mutation, { isRetrying });
}
