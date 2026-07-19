'use client';

import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

import {
  buildIncidentQueue,
  type IncidentQueueRow,
  type RunIncidentBundle,
} from '../lib/incident-model';

/**
 * The API exposes incidents per-run (`listIncidents(runId)`) with no
 * cross-run "all incidents" endpoint. The triage queue therefore fans out over
 * the run list and aggregates client-side. If/when the API gains a dedicated
 * `GET /incidents` endpoint this hook can collapse to a single request.
 */
export function useIncidentQueue() {
  const client = useApiClient();
  return useQuery<IncidentQueueRow[]>({
    queryKey: ['incidents', 'queue'],
    queryFn: async ({ signal }) => {
      const runs = await client.listRuns(signal);
      const bundles = await Promise.all(
        runs.map(async (run): Promise<RunIncidentBundle> => {
          const [incidents, alerts] = await Promise.all([
            client.listIncidents(run.id, signal),
            client.listAlerts(run.id, signal),
          ]);
          return { run, incidents, alerts };
        }),
      );
      return buildIncidentQueue(bundles);
    },
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

export function useIncidentRunAlerts(runId: string | undefined) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.alerts(runId ?? ''),
    queryFn: ({ signal }) => client.listAlerts(runId ?? '', signal),
    enabled: Boolean(runId),
  });
}

/**
 * Rich investigation record (triage, evidence with provenance, hypotheses,
 * proposals, policy decisions, approvals, executions). Absent for incidents
 * that have not been investigated yet — callers treat a 404 as "no activity".
 */
export function useInvestigationDetail(incidentId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.incidents.investigation(incidentId),
    queryFn: ({ signal }) => client.getInvestigationDetail(incidentId, signal),
    enabled: Boolean(incidentId),
    retry: false,
  });
}
