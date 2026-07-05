'use client';

import { useQueries, useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

function collectSessionIds(
  detail: Awaited<ReturnType<ReturnType<typeof useApiClient>['getInvestigationDetail']>>,
): string[] {
  const sessionIds = new Set<string>();
  for (const triage of detail.triageResults) {
    sessionIds.add(triage.sessionId);
  }
  for (const plan of detail.plans) {
    sessionIds.add(plan.sessionId);
  }
  for (const attachment of detail.evidenceAttachments) {
    sessionIds.add(attachment.sessionId);
  }
  for (const note of detail.notes) {
    sessionIds.add(note.sessionId);
  }
  for (const overlay of detail.overlays) {
    sessionIds.add(overlay.sessionId);
  }
  return [...sessionIds];
}

export function useInvestigationDetail(incidentId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.incidents.investigation(incidentId),
    queryFn: ({ signal }) => client.getInvestigationDetail(incidentId, signal),
    enabled: Boolean(incidentId),
  });
}

export function useAgentSession(sessionId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.agentSessions.detail(sessionId),
    queryFn: ({ signal }) => client.getAgentSession(sessionId, signal),
    enabled: Boolean(sessionId),
  });
}

export function useInvestigationAgentSessions(incidentId: string) {
  const investigationQuery = useInvestigationDetail(incidentId);
  const sessionIds = investigationQuery.data ? collectSessionIds(investigationQuery.data) : [];
  const client = useApiClient();

  const sessionQueries = useQueries({
    queries: sessionIds.map((sessionId) => ({
      queryKey: queryKeys.agentSessions.detail(sessionId),
      queryFn: ({ signal }: { signal?: AbortSignal }) => client.getAgentSession(sessionId, signal),
      enabled: Boolean(sessionId),
    })),
  });

  const sessions = sessionQueries
    .map((query) => query.data)
    .filter((session): session is NonNullable<typeof session> => session != null);

  return {
    investigationQuery,
    sessionQueries,
    sessions,
    isPending: investigationQuery.isPending || sessionQueries.some((query) => query.isPending),
    isError: investigationQuery.isError || sessionQueries.some((query) => query.isError),
    refetch: async () => {
      await investigationQuery.refetch();
      await Promise.all(sessionQueries.map((query) => query.refetch()));
    },
  };
}
