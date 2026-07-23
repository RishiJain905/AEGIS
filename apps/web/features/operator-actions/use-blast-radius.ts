'use client';

import { useQuery } from '@tanstack/react-query';

import {
  blastRadiusPreviewSchema,
  parseContract,
  type BlastRadiusPreviewV1,
  type ScenarioCommandTemplateV1,
} from '@aegis/contracts-ts';

import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

async function fetchBlastRadius(
  runId: string,
  command: string,
  assetId: string,
  signal?: AbortSignal,
): Promise<BlastRadiusPreviewV1> {
  const query = new URLSearchParams({ assetId, command });
  const response = await apiFetch(`/api/v1/runs/${runId}/blast-radius?${query.toString()}`, {
    signal,
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
        envelope?.message ?? `Blast-radius preview failed (status ${String(response.status)})`,
      status: response.status,
    });
  }
  return parseContract(blastRadiusPreviewSchema, await response.json());
}

/**
 * Fetch the deterministic blast-radius preview for a (command, asset) pair. Enabled only when
 * the confirm dialog / approval card is open, so it fires on open and never speculatively.
 */
export function useBlastRadius(
  runId: string,
  command: ScenarioCommandTemplateV1 | null,
  assetId: string | null,
  options?: { enabled?: boolean },
) {
  const enabled = (options?.enabled ?? true) && Boolean(runId && command && assetId);
  return useQuery<BlastRadiusPreviewV1, ApiClientError>({
    queryKey: queryKeys.runs.blastRadius(runId, command ?? '', assetId ?? ''),
    queryFn: ({ signal }) => fetchBlastRadius(runId, command as string, assetId as string, signal),
    enabled,
    staleTime: 5_000,
    retry: false,
  });
}
