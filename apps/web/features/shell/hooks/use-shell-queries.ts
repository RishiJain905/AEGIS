'use client';

import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

export function useConnectionStatus() {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.connection.status,
    queryFn: ({ signal }) => client.getConnectionStatus(signal),
    refetchInterval: 30_000,
  });
}

export function useScenarios() {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.scenarios.all,
    queryFn: ({ signal }) => client.listScenarios(signal),
  });
}

export function useScenario(scenarioId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.scenarios.detail(scenarioId),
    queryFn: ({ signal }) => client.getScenario(scenarioId, signal),
    enabled: Boolean(scenarioId),
  });
}

export function useRuns() {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.all,
    queryFn: ({ signal }) => client.listRuns(signal),
  });
}

export function useRun(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.detail(runId),
    queryFn: ({ signal }) => client.getRun(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useRunIncidents(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.incidents(runId),
    queryFn: ({ signal }) => client.listIncidents(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useIncident(incidentId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.incidents.detail(incidentId),
    queryFn: ({ signal }) => client.getIncident(incidentId, signal),
    enabled: Boolean(incidentId),
  });
}

export function useRunGraph(runId: string, options?: { enabled?: boolean }) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.graph(runId),
    queryFn: ({ signal }) => client.getRunGraph(runId, signal),
    enabled: options?.enabled ?? Boolean(runId),
  });
}

export function useRunReadOnly(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.readOnly(runId),
    queryFn: ({ signal }) => client.isReadOnly(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useRunAlerts(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.alerts(runId),
    queryFn: ({ signal }) => client.listAlerts(runId, signal),
    enabled: Boolean(runId),
  });
}
