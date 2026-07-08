'use client';

import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

export function useAfterActionReport(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.afterActionReport(runId),
    queryFn: ({ signal }) => client.getAfterActionReport(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useReportVersions(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.reportVersions(runId),
    queryFn: ({ signal }) => client.listAfterActionReportVersions(runId, signal),
    enabled: Boolean(runId),
  });
}
