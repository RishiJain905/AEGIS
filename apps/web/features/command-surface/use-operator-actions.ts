'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

import type {
  OperatorActionRequest,
  OperatorActionResponse,
  RulesOfEngagement,
  RunLoadout,
  ScenarioCommandTemplate,
} from './contracts';

function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
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
  return (await response.json()) as T;
}

export interface SubmitOperatorActionInput {
  command: ScenarioCommandTemplate;
  targetAssetId: string;
  reason: string;
  /** Present + true acknowledges the consequences of a Class 2/3 action (approve+execute). */
  confirm?: boolean;
  incidentId?: string | null;
}

/**
 * Submit a player-initiated containment action.
 *
 * Routes through the same policy → approval → execution pipeline as agent proposals. Class
 * 0/1 auto-execute; Class 2/3 return `confirmation_required` unless `confirm: true` is sent
 * (the operator is the incident commander approving their own call). A policy block is a
 * successful HTTP response with `status: 'blocked'` — surfaced honestly, not thrown.
 * Feed/graph queries are invalidated on success so the action shows in the room immediately.
 */
export function useSubmitOperatorAction(runId: string) {
  const queryClient = useQueryClient();

  return useMutation<OperatorActionResponse, ApiClientError, SubmitOperatorActionInput>({
    mutationFn: (input) => {
      const request: OperatorActionRequest = {
        schemaVersion: 1,
        scenarioCommand: input.command,
        targetAssetId: input.targetAssetId,
        reason: input.reason,
        confirm: input.confirm ?? false,
        incidentId: input.incidentId ?? null,
        idempotencyKey: newIdempotencyKey('op-action'),
      };
      return postJson<OperatorActionResponse>(
        `/api/v1/runs/${runId}/operator-actions`,
        request,
      );
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs', runId, 'ops-feed'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.runs.graph(runId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.runs.incidents(runId) }),
      ]);
    },
  });
}

/**
 * Change the run's rules-of-engagement dial mid-run (PATCH /runs/{id}/roe). Audited via a
 * `run.roe_changed` domain event; returns the updated run. Run detail is invalidated so the
 * header and status strip reflect the new doctrine level.
 */
export function useChangeRoe(runId: string) {
  const queryClient = useQueryClient();

  return useMutation<unknown, ApiClientError, RulesOfEngagement>({
    mutationFn: async (roe) => {
      const response = await apiFetch(`/api/v1/runs/${runId}/roe`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schemaVersion: 1, roe }),
      });
      if (!response.ok) {
        let envelope: { code?: string; message?: string } | undefined;
        try {
          envelope = (await response.json()) as typeof envelope;
        } catch {
          envelope = undefined;
        }
        throw new ApiClientError({
          code: envelope?.code ?? 'HTTP_ERROR',
          message: envelope?.message ?? `Failed to change RoE (status ${String(response.status)})`,
          status: response.status,
        });
      }
      return (await response.json()) as unknown;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.runs.detail(runId) }),
        queryClient.invalidateQueries({ queryKey: ['runs', runId, 'ops-feed'] }),
      ]);
    },
  });
}

/**
 * Read the run's persisted loadout (bias guard, threat tempo, RoE) off the run detail.
 * Optional/absent on legacy runs → callers treat a missing value as the default loadout.
 */
export function readRunLoadout(run: unknown): RunLoadout | null {
  if (typeof run !== 'object' || run === null) {
    return null;
  }
  const loadout = (run as { loadout?: unknown }).loadout;
  if (typeof loadout !== 'object' || loadout === null) {
    return null;
  }
  const value = loadout as Partial<RunLoadout>;
  if (typeof value.roe !== 'string') {
    return null;
  }
  return {
    schemaVersion: typeof value.schemaVersion === 'number' ? value.schemaVersion : 1,
    biasGuard: value.biasGuard !== false,
    threatTempo: value.threatTempo !== false,
    roe: value.roe,
  };
}
