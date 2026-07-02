'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
}

function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`;
}

interface RunCommandJsonResponse {
  run: { id: string; status: string };
  eventsEmitted: number;
}

async function postRunCommand(
  path: string,
  idempotencyKey: string,
): Promise<RunCommandJsonResponse> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
  });
  if (!response.ok) {
    let envelope;
    try {
      envelope = (await response.json()) as {
        code?: string;
        message?: string;
        traceId?: string;
      };
    } catch {
      throw new ApiClientError({
        code: 'HTTP_ERROR',
        message: `Request failed with status ${String(response.status)}`,
        status: response.status,
      });
    }
    throw new ApiClientError({
      code: envelope.code ?? 'HTTP_ERROR',
      message: envelope.message ?? 'Run command failed',
      status: response.status,
      traceId: envelope.traceId,
    });
  }
  return (await response.json()) as RunCommandJsonResponse;
}

export function useRunCommands(runId: string) {
  const queryClient = useQueryClient();

  const invalidate = async () => {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.runs.detail(runId),
    });
    await queryClient.invalidateQueries({
      queryKey: queryKeys.runs.graph(runId),
    });
  };

  const pause = useMutation({
    mutationFn: () => postRunCommand(`/api/v1/runs/${runId}/pause`, newIdempotencyKey('pause')),
    onSuccess: () => void invalidate(),
  });

  const resume = useMutation({
    mutationFn: () => postRunCommand(`/api/v1/runs/${runId}/resume`, newIdempotencyKey('resume')),
    onSuccess: () => void invalidate(),
  });

  const stop = useMutation({
    mutationFn: () => postRunCommand(`/api/v1/runs/${runId}/stop`, newIdempotencyKey('stop')),
    onSuccess: () => void invalidate(),
  });

  const step = useMutation({
    mutationFn: () => postRunCommand(`/api/v1/runs/${runId}/step`, newIdempotencyKey('step')),
    onSuccess: () => void invalidate(),
  });

  return { pause, resume, stop, step };
}

export function useCreateRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: { scenarioPackagePath: string; seed: number }) => {
      const response = await fetch(`${getApiBaseUrl()}/api/v1/runs`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'Idempotency-Key': newIdempotencyKey('create'),
        },
        body: JSON.stringify({
          schemaVersion: 1,
          scenarioPackagePath: input.scenarioPackagePath,
          seed: input.seed,
        }),
      });
      if (!response.ok) {
        throw new ApiClientError({
          code: 'HTTP_ERROR',
          message: `Failed to create run: ${String(response.status)}`,
          status: response.status,
        });
      }
      const body: unknown = await response.json();
      if (
        typeof body !== 'object' ||
        body === null ||
        !('run' in body) ||
        typeof (body as { run?: { id?: unknown } }).run?.id !== 'string'
      ) {
        throw new ApiClientError({
          code: 'HTTP_ERROR',
          message: 'Invalid create run response',
          status: response.status,
        });
      }
      return body as { run: { id: string } };
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}
