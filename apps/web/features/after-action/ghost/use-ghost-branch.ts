'use client';

/**
 * Ghost branch data hooks — the after-action counterfactual-replay panel's only I/O.
 *
 * Both endpoints are ownership-gated on the server AND refuse until the run is terminal
 * (409 `RUN_NOT_TERMINAL`). The decision-points query mirrors that contract client-side: it
 * is enabled only once the caller has confirmed the run is terminal, so a live run never
 * even requests the fork points. The mutation surfaces a typed {@link ApiClientError} whose
 * `code` the panel special-cases (e.g. `RUN_NOT_TERMINAL`).
 */

import { useMutation, useQuery } from '@tanstack/react-query';

import {
  ghostBranchResultSchema,
  ghostDecisionPointsSchema,
  parseContract,
  type GhostBranchRequestV1,
  type GhostBranchResultV1,
  type GhostDecisionPointsV1,
} from '@aegis/contracts-ts';

import { apiFetch, apiFetchJson } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

/**
 * Fetch the run's forkable decision points. `terminal` gates the request: while the run is
 * live the query stays disabled so ground truth is never pulled to the client.
 */
export function useGhostDecisionPoints(runId: string, terminal: boolean) {
  return useQuery({
    queryKey: queryKeys.runs.decisionPoints(runId),
    queryFn: ({ signal }) =>
      apiFetchJson<GhostDecisionPointsV1>(
        `/api/v1/runs/${encodeURIComponent(runId)}/ghost/decision-points`,
        { signal },
        (data) => parseContract(ghostDecisionPointsSchema, data),
      ),
    enabled: Boolean(runId) && terminal,
    staleTime: 5 * 60_000,
  });
}

/**
 * POST a ghost-branch request. Mirrors the approval-mutation error idiom but reads the code
 * from either the standard envelope (`code`) or a FastAPI dict detail (`detail.code`) so the
 * panel can special-case `RUN_NOT_TERMINAL` and the engine's typed errors.
 */
async function postGhostJson(
  path: string,
  body: GhostBranchRequestV1,
): Promise<GhostBranchResultV1> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let code = 'HTTP_ERROR';
    let message = `Request failed with status ${String(response.status)}`;
    let traceId: string | undefined;
    try {
      const raw = (await response.json()) as Record<string, unknown>;
      const detail = raw.detail;
      if (detail && typeof detail === 'object') {
        const d = detail as Record<string, unknown>;
        if (typeof d.code === 'string') {
          code = d.code;
        }
        if (typeof d.message === 'string') {
          message = d.message;
        }
      }
      // A standard error envelope carries the code/message at the top level; prefer it.
      if (typeof raw.code === 'string') {
        code = raw.code;
      }
      if (typeof raw.message === 'string') {
        message = raw.message;
      }
      if (typeof raw.traceId === 'string') {
        traceId = raw.traceId;
      }
    } catch {
      /* non-JSON body — fall back to the status-derived defaults */
    }
    throw new ApiClientError({ code, message, status: response.status, traceId });
  }
  const data: unknown = await response.json();
  return parseContract(ghostBranchResultSchema, data);
}

export function useGhostRunMutation(runId: string) {
  return useMutation<GhostBranchResultV1, ApiClientError, GhostBranchRequestV1>({
    mutationFn: (request) =>
      postGhostJson(`/api/v1/runs/${encodeURIComponent(runId)}/ghost`, request),
  });
}
