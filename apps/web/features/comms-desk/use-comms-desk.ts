'use client';

import { useMemo } from 'react';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  agentSessionDetailSchema,
  parseContract,
  type AgentSessionDetailV1,
} from '@aegis/contracts-ts';

import { newTraceId, useRunAgentSessions } from '@/features/agent-chat/use-agent-chat';
import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

/** One rendered situation report: the prose brief plus its grounding, from a SCRIBE task. */
export interface Sitrep {
  taskId: string;
  sessionId: string;
  status: string;
  createdAt: string;
  completedAt: string | null;
  /** Leadership brief prose (the run-scoped step's rationale), empty until the turn finishes. */
  brief: string;
  evidenceIds: string[];
  confidence: number | null;
}

function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`;
}

const SCRIBE_ROLE = 'SCRIBE';

/** Canned, timestamped SITREP directive fed to the run-scoped SCRIBE turn as operator intent. */
export function buildSitrepInstruction(now: Date = new Date()): string {
  const stamp = now.toISOString();
  return (
    `SITREP requested at ${stamp}. Compile a leadership-ready situation report from the ` +
    'current live evidence: the incident state, the key detections and evidence so far, the ' +
    'actions taken (operator and agents), the present risk, and the recommended next steps. ' +
    'Ground every factual claim in evidence IDs. Be explicit about what is still unknown or ' +
    'uncertain. Prose only — do not approve or recommend executing containment.'
  );
}

function readEvidenceIds(payload: Record<string, unknown>): string[] {
  const citations = payload.evidenceCitations;
  if (!Array.isArray(citations)) {
    return [];
  }
  const ids: string[] = [];
  for (const entry of citations as unknown[]) {
    if (entry !== null && typeof entry === 'object' && 'evidenceId' in entry) {
      const value = entry.evidenceId;
      if (typeof value === 'string') {
        ids.push(value);
      }
    }
  }
  return ids;
}

function readConfidence(payload: Record<string, unknown>): number | null {
  return typeof payload.confidence === 'number' ? payload.confidence : null;
}

/**
 * Derive the ordered SITREP history for a run from the SCRIBE agent session(s). Each SCRIBE
 * task is one sitrep; its STEP_RESULT artifact (when the turn has finished) carries the brief
 * prose and evidence citations. Newest first.
 */
export function useSitrepHistory(runId: string): {
  sitreps: Sitrep[];
  isLoading: boolean;
  isError: boolean;
} {
  // SITREPs are operator-requested SCRIBE turns; share the copilot's operator-scoped
  // query rather than pulling every autonomy triage session along with them.
  const query = useRunAgentSessions(runId, 'operator');

  const sitreps = useMemo<Sitrep[]>(() => {
    const sessions: AgentSessionDetailV1[] = query.data ?? [];
    const scribeSessions = sessions.filter((detail) => detail.session.role === SCRIBE_ROLE);
    const items: Sitrep[] = [];
    for (const detail of scribeSessions) {
      const artifactByTask = new Map<string, Record<string, unknown>>();
      for (const artifact of detail.artifacts) {
        // Latest artifact per task wins (a task emits one STEP_RESULT on success).
        artifactByTask.set(artifact.taskId, artifact.payload);
      }
      for (const task of detail.tasks) {
        const payload = artifactByTask.get(task.id);
        const brief = payload && typeof payload.rationale === 'string' ? payload.rationale : '';
        items.push({
          taskId: task.id,
          sessionId: detail.session.id,
          status: task.status,
          createdAt: task.createdAt,
          completedAt: task.completedAt ?? null,
          brief,
          evidenceIds: payload ? readEvidenceIds(payload) : [],
          confidence: payload ? readConfidence(payload) : null,
        });
      }
    }
    items.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    return items;
  }, [query.data]);

  return { sitreps, isLoading: query.isLoading, isError: query.isError };
}

async function createScribeSession(
  runId: string,
  instructions: string,
  signal?: AbortSignal,
): Promise<AgentSessionDetailV1> {
  const response = await apiFetch(`/api/v1/runs/${runId}/agent-sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schemaVersion: 1,
      role: SCRIBE_ROLE,
      traceId: newTraceId(),
      enqueueInitialTask: true,
      providerId: null,
      instructions,
    }),
    signal,
  });
  if (!response.ok) {
    throw new ApiClientError({
      code: 'HTTP_ERROR',
      message: `SITREP request failed (status ${String(response.status)})`,
      status: response.status,
    });
  }
  return parseContract(agentSessionDetailSchema, await response.json());
}

async function appendScribeTask(
  sessionId: string,
  instructions: string,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch(`/api/v1/agent-sessions/${sessionId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schemaVersion: 1,
      idempotencyKey: newIdempotencyKey('sitrep'),
      providerId: null,
      instructions,
    }),
    signal,
  });
  if (!response.ok) {
    throw new ApiClientError({
      code: 'HTTP_ERROR',
      message: `SITREP request failed (status ${String(response.status)})`,
      status: response.status,
    });
  }
}

/**
 * Request a new SITREP. Reuses the run's SCRIBE session (one thread per run) when it exists,
 * appending a task; otherwise opens the session with an initial task. The turn runs inline
 * server-side (slow on the local 27B), so callers surface a compiling state while pending and
 * refetch the run's sessions on success to render the brief.
 */
export function useRequestSitrep(runId: string) {
  const queryClient = useQueryClient();
  const sessions = useRunAgentSessions(runId, 'operator');

  return useMutation<boolean, ApiClientError>({
    mutationFn: async (): Promise<boolean> => {
      const instructions = buildSitrepInstruction();
      const existing = (sessions.data ?? []).find((detail) => detail.session.role === SCRIBE_ROLE);
      if (existing) {
        await appendScribeTask(existing.session.id, instructions);
      } else {
        await createScribeSession(runId, instructions);
      }
      return true;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.agentSessions.listForRun(runId),
      });
    },
  });
}
