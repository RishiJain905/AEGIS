'use client';

import { useMemo } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { hypothesisSchema, parseContract, type HypothesisV1 } from '@aegis/contracts-ts';

import { useRunAgentSessions } from '@/features/agent-chat/use-agent-chat';
import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

import { buildHypothesisLedger, type HypothesisLedger } from './ledger-model';

async function fetchConsoleHypotheses(
  runId: string,
  signal?: AbortSignal,
): Promise<HypothesisV1[]> {
  const response = await apiFetch(`/api/v1/runs/${runId}/console/hypotheses`, { signal });
  if (!response.ok) {
    throw new ApiClientError({
      code: 'HTTP_ERROR',
      message: `Failed to load hypotheses (status ${String(response.status)})`,
      status: response.status,
    });
  }
  const body = (await response.json()) as { hypotheses?: unknown[] };
  const raw = Array.isArray(body.hypotheses) ? body.hypotheses : [];
  return raw.map((entry) => parseContract(hypothesisSchema, entry));
}

/** Operator-pinned (and any incident-anchored agent) hypotheses persisted for the run. */
export function useConsoleHypotheses(runId: string) {
  return useQuery<HypothesisV1[], ApiClientError>({
    queryKey: queryKeys.runs.consoleHypotheses(runId),
    queryFn: ({ signal }) => fetchConsoleHypotheses(runId, signal),
    enabled: Boolean(runId),
    staleTime: 3_000,
  });
}

export interface CreateHypothesisInput {
  statement: string;
  assetIds: string[];
  confidence: number;
}

/** Pin an operator hypothesis into the shared evidence pool the agents (and bias guard) read. */
export function useCreateHypothesis(runId: string) {
  const queryClient = useQueryClient();
  return useMutation<HypothesisV1, ApiClientError, CreateHypothesisInput>({
    mutationFn: async (input) => {
      const response = await apiFetch(`/api/v1/runs/${runId}/console/hypotheses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schemaVersion: 1,
          statement: input.statement,
          assetIds: input.assetIds,
          confidence: input.confidence,
        }),
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
          message:
            envelope?.message ?? `Failed to pin hypothesis (status ${String(response.status)})`,
          status: response.status,
        });
      }
      return parseContract(hypothesisSchema, await response.json());
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.runs.consoleHypotheses(runId),
      });
    },
  });
}

/** Combined ledger: persisted hypotheses + bias-guard challenges from the run's agent sessions. */
export function useHypothesisLedger(runId: string): {
  ledger: HypothesisLedger;
  isLoading: boolean;
  isError: boolean;
} {
  const hypotheses = useConsoleHypotheses(runId);
  // Unfiltered on purpose: bias-guard challenges come from the autonomy worker's own
  // ORACLE sessions, so narrowing this to operator threads would empty the ledger's
  // CHALLENGED badges.
  const sessions = useRunAgentSessions(runId);

  const ledger = useMemo(
    () => buildHypothesisLedger(hypotheses.data ?? [], sessions.data ?? []),
    [hypotheses.data, sessions.data],
  );

  return {
    ledger,
    isLoading: hypotheses.isLoading,
    isError: hypotheses.isError,
  };
}
