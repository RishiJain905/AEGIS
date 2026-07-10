'use client';

import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

export function useAfterActionView(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.afterAction(runId),
    queryFn: ({ signal }) => client.getAfterAction(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useRunScore(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.score(runId),
    queryFn: ({ signal }) => client.getRunScore(runId, signal),
    enabled: Boolean(runId),
  });
}
