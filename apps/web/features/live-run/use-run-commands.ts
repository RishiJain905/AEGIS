'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

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
  const response = await apiFetch(path, {
    method: 'POST',
    headers: {
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

/**
 * Resume a paused run outside a component that owns a `useRunCommands` hook — e.g. the
 * scenarios catalogue, which resumes the latest owned run before navigating into it.
 */
export async function resumeRun(runId: string): Promise<void> {
  await postRunCommand(`/api/v1/runs/${runId}/resume`, newIdempotencyKey('resume'));
}

/**
 * Per-run capability loadout chosen at launch. Additive optional field on POST /runs
 * (schemaVersion stays 1): when omitted the server persists the default loadout. Typed
 * loosely here to avoid depending on the interim command-surface contract from the live-run
 * feature; the launch flow passes a fully-formed loadout object.
 */
export interface CreateRunLoadout {
  schemaVersion: number;
  biasGuard: boolean;
  threatTempo: boolean;
  roe: string;
}

export function useCreateRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: {
      scenarioPackagePath: string;
      seed?: number;
      loadout?: CreateRunLoadout;
      commanderIntent?: string;
      /**
       * Pinned-seed scenarios derive one run id per (seed, scenarioVersion) forever, so
       * relaunching one otherwise resumes the run created the first time. Set this to have
       * the server destroy that run and build it again from scratch. Only meaningful for a
       * pinned seed; seedless launches always get a brand-new run id.
       */
      restartExisting?: boolean;
    }) => {
      const response = await apiFetch('/api/v1/runs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': newIdempotencyKey('create'),
        },
        body: JSON.stringify({
          schemaVersion: 1,
          scenarioPackagePath: input.scenarioPackagePath,
          // Omit seed entirely to let the server draw a cryptographically random one.
          ...(input.seed !== undefined ? { seed: input.seed } : {}),
          // Omit loadout entirely to let the server persist the default loadout.
          ...(input.loadout !== undefined ? { loadout: input.loadout } : {}),
          // Omit commanderIntent entirely when the operator skipped it.
          ...(input.commanderIntent !== undefined
            ? { commanderIntent: input.commanderIntent }
            : {}),
          // Omit entirely unless restarting, so every other caller keeps today's behaviour.
          ...(input.restartExisting ? { restartExisting: true } : {}),
        }),
      });
      if (!response.ok) {
        // Keep the server's own code and message. A launch can fail for a reason the
        // operator can act on — most importantly RUN_OWNED_BY_ANOTHER_USER, where a
        // pinned-seed scenario's single run id already belongs to someone else — and
        // flattening every failure to "Failed to create run: 409" hides that.
        let envelope: { code?: string; message?: string; traceId?: string } | undefined;
        try {
          envelope = (await response.json()) as typeof envelope;
        } catch {
          envelope = undefined;
        }
        throw new ApiClientError({
          code: envelope?.code ?? 'HTTP_ERROR',
          message: envelope?.message ?? `Failed to create run: ${String(response.status)}`,
          status: response.status,
          traceId: envelope?.traceId,
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
