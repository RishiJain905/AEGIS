'use client';

import { useEffect, useMemo, useRef } from 'react';

import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api/query-keys';
import { useApiClient } from '@/lib/api/api-client-provider';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import type { TutorialEvidence } from './tutorial-machine';
import { EMPTY_EVIDENCE } from './tutorial-machine';

const POLL_INTERVAL_MS = 4000;
const TERMINAL_RUN_STATUSES = new Set(['completed', 'stopped', 'failed', 'aborted']);
const TERMINAL_PROPOSAL_STATUSES = new Set(['approved', 'rejected', 'executed', 'cancelled']);

export interface TutorialRunObservation {
  /** The run's scenario-version id, used to detect the training scenario. */
  scenarioVersionId?: string;
  /** Whether the run detail has resolved at least once. */
  runReady: boolean;
  /** Evidence with `welcomeAcknowledged` left false — the controller folds that in. */
  evidence: TutorialEvidence;
  /** The incident the operator is engaging, if any (used for the report-back copy). */
  activeIncidentId: string | null;
}

function extractIncidentRouteId(pathname: string | null): string | null {
  if (!pathname) {
    return null;
  }
  const match = /\/incidents\/([^/?#]+)/.exec(pathname);
  const captured = match?.[1];
  return captured ? decodeURIComponent(captured) : null;
}

/**
 * Observe a live run and project it onto the tutorial evidence shape. The heavy polling
 * queries only run while `enabled` (a confirmed, in-progress training run), so the hook
 * is inert on every other shell page. Runs outside the LiveRunProvider (shell-level
 * mount), so it self-polls rather than relying on websocket-driven invalidations.
 */
export function useTutorialEvidence(
  runId: string | null,
  enabled: boolean,
): TutorialRunObservation {
  const client = useApiClient();
  const pathname = usePathname();

  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const selectedIncidentId = useWorkspaceUiStore((state) => state.workspace.selectedIncidentId);

  const runQuery = useQuery({
    queryKey: queryKeys.runs.detail(runId ?? ''),
    queryFn: ({ signal }) => client.getRun(runId ?? '', signal),
    enabled: Boolean(runId),
    refetchInterval: enabled ? POLL_INTERVAL_MS : false,
  });

  const alertsQuery = useQuery({
    queryKey: queryKeys.runs.alerts(runId ?? ''),
    queryFn: ({ signal }) => client.listAlerts(runId ?? '', signal),
    enabled: enabled && Boolean(runId),
    refetchInterval: enabled ? POLL_INTERVAL_MS : false,
  });

  const incidentsQuery = useQuery({
    queryKey: queryKeys.runs.incidents(runId ?? ''),
    queryFn: ({ signal }) => client.listIncidents(runId ?? '', signal),
    enabled: enabled && Boolean(runId),
    refetchInterval: enabled ? POLL_INTERVAL_MS : false,
  });

  const runStatus = runQuery.data?.status;
  const runComplete = runStatus ? TERMINAL_RUN_STATUSES.has(runStatus) : false;

  // Telemetry is "flowing" once new simulation time has been observed since the operator
  // arrived — a real transition, so a fresh run dwells briefly on the watch step rather
  // than leaping straight past it.
  const baselineSimTimeRef = useRef<string | null>(null);
  const telemetryFlowingRef = useRef(false);
  const simTime = runQuery.data?.simTime ?? null;
  useEffect(() => {
    if (!enabled) {
      baselineSimTimeRef.current = null;
      telemetryFlowingRef.current = false;
      return;
    }
    if (simTime == null) {
      return;
    }
    if (baselineSimTimeRef.current == null) {
      baselineSimTimeRef.current = simTime;
      return;
    }
    if (simTime > baselineSimTimeRef.current) {
      telemetryFlowingRef.current = true;
    }
  }, [enabled, simTime]);

  const incidents = incidentsQuery.data ?? [];
  const incidentIds = useMemo(
    () => new Set(incidents.map((incident: { id: string }) => incident.id)),
    [incidents],
  );

  const routeIncidentId = extractIncidentRouteId(pathname);
  const selectedIsIncident = selectedEntityId != null && incidentIds.has(selectedEntityId);
  const incidentOpened =
    routeIncidentId != null || selectedIncidentId != null || selectedIsIncident;

  const activeIncidentId =
    routeIncidentId ??
    selectedIncidentId ??
    (selectedIsIncident ? selectedEntityId : null) ??
    incidents[0]?.id ??
    null;

  const investigationQuery = useQuery({
    queryKey: queryKeys.incidents.investigation(activeIncidentId ?? ''),
    queryFn: ({ signal }) => client.getInvestigationDetail(activeIncidentId ?? '', signal),
    enabled: enabled && Boolean(activeIncidentId),
    refetchInterval: enabled ? POLL_INTERVAL_MS : false,
  });

  const detail = investigationQuery.data;
  const agentTaskCreated = detail
    ? detail.triageResults.length > 0 ||
      detail.plans.length > 0 ||
      detail.notes.length > 0 ||
      detail.evidenceAttachments.length > 0 ||
      detail.overlays.length > 0
    : false;
  const containmentResolved = detail
    ? detail.approvals.length > 0 ||
      detail.executedActions.length > 0 ||
      detail.proposals.some((proposal: { status: string }) =>
        TERMINAL_PROPOSAL_STATUSES.has(proposal.status),
      )
    : false;

  const evidence: TutorialEvidence = enabled
    ? {
        welcomeAcknowledged: false,
        telemetryFlowing: telemetryFlowingRef.current,
        alertRaised: (alertsQuery.data?.length ?? 0) > 0,
        incidentOpened,
        agentTaskCreated,
        containmentResolved,
        runComplete,
      }
    : EMPTY_EVIDENCE;

  return {
    scenarioVersionId: runQuery.data?.scenarioVersionId,
    runReady: runQuery.isSuccess,
    evidence,
    activeIncidentId,
  };
}
