'use client';

import { useQuery } from '@tanstack/react-query';

import type { AlertV1, IncidentV1, RunV1 } from '@aegis/contracts-ts';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

import {
  buildIncidentQueue,
  type IncidentQueueRow,
  type RunIncidentBundle,
} from '../lib/incident-model';

/**
 * Cap on parallel alert reads. The queue previously fanned out over *every* run —
 * `2N + 1` simultaneous requests — which crossed the API's per-session burst limit
 * (30 tokens, refilled 2/s) once a handful of runs existed. `Promise.all` then
 * rejected on the first 429 and the whole page rendered "Unable to load incidents",
 * even though the incidents themselves were fine. Incidents now arrive in one
 * cross-run request; alerts are read only for the runs that actually have an
 * incident, a few at a time.
 */
const ALERT_FETCH_CONCURRENCY = 4;

async function mapWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const queue = items.map((item, index) => [index, item] as const);
  const results = new Array<R>(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    for (;;) {
      const entry = queue[cursor];
      cursor += 1;
      if (!entry) {
        return;
      }
      const [index, item] = entry;
      results[index] = await fn(item);
    }
  });
  await Promise.all(workers);
  return results;
}

/**
 * The cross-run triage queue: incidents for every run the operator may read.
 *
 * Alerts only supply each row's severity, so a run whose alerts fail to load still
 * contributes its incidents — the row degrades to the lowest severity rather than
 * taking the page down with it. A failure to read the runs or the incidents
 * themselves is fatal, because there is no queue to show without them.
 */
export function useIncidentQueue() {
  const client = useApiClient();
  return useQuery<IncidentQueueRow[]>({
    queryKey: ['incidents', 'queue'],
    queryFn: async ({ signal }) => {
      const [runs, incidents] = await Promise.all([
        client.listRuns(signal),
        client.listAllIncidents(signal),
      ]);
      const runsById = new Map(runs.map((run) => [run.id, run]));
      const grouped = new Map<RunV1, IncidentV1[]>();
      for (const incident of incidents) {
        // Incidents are scoped to the same runs `listRuns` returns, so a miss here means
        // the run vanished between the two reads; there is no row to render without it.
        const run = runsById.get(incident.runId);
        if (!run) {
          continue;
        }
        const existing = grouped.get(run);
        if (existing) {
          existing.push(incident);
        } else {
          grouped.set(run, [incident]);
        }
      }

      const entries = [...grouped.entries()];
      const alertsPerRun = await mapWithConcurrency(
        entries,
        ALERT_FETCH_CONCURRENCY,
        async ([run]): Promise<AlertV1[]> => {
          try {
            return await client.listAlerts(run.id, signal);
          } catch {
            return [];
          }
        },
      );

      return buildIncidentQueue(
        entries.map(
          ([run, runIncidents], index): RunIncidentBundle => ({
            run,
            incidents: runIncidents,
            alerts: alertsPerRun[index] ?? [],
          }),
        ),
      );
    },
  });
}

/**
 * Incidents opened on a single run. Backs the copilot's BASTION prerequisite check —
 * BASTION's proposal tooling is incident-scoped, so with no open case its turn can only
 * end in a rejected tool call.
 */
export function useRunIncidents(runId: string | undefined) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.incidents(runId ?? ''),
    queryFn: ({ signal }) => client.listIncidents(runId ?? '', signal),
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
