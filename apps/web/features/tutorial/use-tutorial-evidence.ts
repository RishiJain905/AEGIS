'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';

import { useRunAgentSessions } from '@/features/agent-chat/use-agent-chat';
import { queryKeys } from '@/lib/api/query-keys';
import { useApiClient } from '@/lib/api/api-client-provider';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import {
  EMPTY_EVIDENCE,
  type TutorialEvidence,
  type TutorialEvidenceKey,
} from './tutorial-contract';
import { isRunTerminal } from './tutorial-run-clock';

const POLL_INTERVAL_MS = 4000;
/**
 * How often the run detail is refreshed purely to watch the simulation clock.
 *
 * Deliberately much slower than the objective polling: the clock crosses the hold threshold
 * once in a run that takes about eleven minutes, so second-level precision buys nothing, and
 * this query's key is the one `ShellRouteGuard` gates the whole shell on — every observer of
 * it pays for the interval chosen here.
 */
const CLOCK_WATCH_POLL_INTERVAL_MS = 15_000;
const TERMINAL_PROPOSAL_STATUSES = new Set(['approved', 'rejected', 'executed', 'cancelled']);
/** The after-action report only exists once SCRIBE has run, which needs a finished run. */
const REPORT_ELIGIBLE_RUN_STATUSES = new Set(['completed', 'stopped']);
/** Class 0/1 commands. Anything else executed is a containment action (Class 2+). */
const LOW_IMPACT_COMMANDS = new Set(['observe', 'increase_monitoring']);

/**
 * Which evidence keys each backing query answers. The walkthrough only runs a query while a
 * beat the operator has actually reached is still waiting on one of its keys, so the polling
 * cost tracks where they are in the tour rather than being always-on.
 *
 * This matters more than it looks: the run-detail query below shares its key with the one
 * `ShellRouteGuard` gates the whole shell on, so an ungated interval here re-fetches for
 * every observer of that key across the app.
 */
const RUN_STATUS_KEYS: readonly TutorialEvidenceKey[] = [
  'telemetryFlowing',
  'runComplete',
  // Report readiness is gated on the run being terminal, so it needs the status too.
  'reportReady',
];
const ALERT_KEYS: readonly TutorialEvidenceKey[] = ['alertRaised'];
const INVESTIGATION_KEYS: readonly TutorialEvidenceKey[] = [
  'operatorActionExecuted',
  'containmentActionExecuted',
  'proposalRaised',
  'containmentResolved',
];
const AGENT_KEYS: readonly TutorialEvidenceKey[] = ['agentTaskCreated', 'agentReplyReceived'];
const REPORT_KEYS: readonly TutorialEvidenceKey[] = ['reportReady'];

export interface TutorialObservationInput {
  /**
   * Master switch. True only for a confirmed, non-dismissed training run whose walkthrough is
   * still in flight; false stands every query below down.
   */
  enabled: boolean;
  /**
   * Evidence keys still outstanding on beats the operator has reached (see
   * `pendingObjectiveKeys`). Queries are gated on these — an empty list means no polling.
   */
  pendingKeys: readonly TutorialEvidenceKey[];
  /**
   * Keep the run detail fresh enough to see the simulation clock approach its horizon, and to
   * notice the run going terminal (see `shouldWatchRunClock`). Reuses the run-detail query
   * already declared below rather than adding one, and only slows to
   * `CLOCK_WATCH_POLL_INTERVAL_MS` when the objective polling is not already running faster.
   */
  watchRunClock: boolean;
}

export interface TutorialRunObservation {
  /** The run's scenario-version id, used to detect the training scenario. */
  scenarioVersionId?: string;
  /** The run's lifecycle status, or `null` until the run detail resolves. */
  runStatus: string | null;
  /** The run's current virtual clock as an absolute instant, or `null` until it resolves. */
  simTime: string | null;
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

function needsAny(
  pendingKeys: readonly TutorialEvidenceKey[],
  keys: readonly TutorialEvidenceKey[],
): boolean {
  return keys.some((key) => pendingKeys.includes(key));
}

/**
 * Observe a live run and project it onto the tutorial evidence shape.
 *
 * Runs at shell level, outside the per-run LiveRunProvider, so it self-polls the same
 * TanStack queries the live surfaces use rather than relying on websocket invalidations —
 * and shares their cache entries, so on the run page most of this costs nothing extra.
 *
 * Evidence here is a snapshot of the world, not a record of what the operator has done: a
 * value can go false again (an asset gets deselected, a stood-down query drops its data).
 * Permanence lives in the machine's `completedBeatIds`, which only ever grows.
 */
export function useTutorialEvidence(
  runId: string | null,
  { enabled, pendingKeys, watchRunClock }: TutorialObservationInput,
): TutorialRunObservation {
  const client = useApiClient();
  const pathname = usePathname();

  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const selectedIncidentId = useWorkspaceUiStore((state) => state.workspace.selectedIncidentId);
  const graphOptionsOpened = useWorkspaceUiStore((state) => state.graphViewOptionsOpen);

  const needsRunStatus = enabled && needsAny(pendingKeys, RUN_STATUS_KEYS);
  const needsAlerts = enabled && needsAny(pendingKeys, ALERT_KEYS);
  const needsInvestigation = enabled && needsAny(pendingKeys, INVESTIGATION_KEYS);
  const needsAgents = enabled && needsAny(pendingKeys, AGENT_KEYS);
  const needsReport = enabled && needsAny(pendingKeys, REPORT_KEYS);

  // The run detail resolves once for every run so the controller can tell whether this is the
  // training scenario at all; only the *interval* is gated, since that is what costs. Two
  // things want the interval — an outstanding run-status objective, and the clock watch — and
  // they share one query at whichever cadence is the faster of the two currently asked for.
  const runQuery = useQuery({
    queryKey: queryKeys.runs.detail(runId ?? ''),
    queryFn: ({ signal }) => client.getRun(runId ?? '', signal),
    enabled: Boolean(runId),
    refetchInterval: needsRunStatus
      ? POLL_INTERVAL_MS
      : enabled && watchRunClock
        ? CLOCK_WATCH_POLL_INTERVAL_MS
        : false,
  });

  const alertsQuery = useQuery({
    queryKey: queryKeys.runs.alerts(runId ?? ''),
    queryFn: ({ signal }) => client.listAlerts(runId ?? '', signal),
    enabled: needsAlerts && Boolean(runId),
    refetchInterval: needsAlerts ? POLL_INTERVAL_MS : false,
  });

  const incidentsQuery = useQuery({
    queryKey: queryKeys.runs.incidents(runId ?? ''),
    queryFn: ({ signal }) => client.listIncidents(runId ?? '', signal),
    enabled: needsInvestigation && Boolean(runId),
    refetchInterval: needsInvestigation ? POLL_INTERVAL_MS : false,
  });

  const runStatus = runQuery.data?.status;
  const runComplete = isRunTerminal(runStatus);

  // Telemetry is "flowing" once new simulation time has been observed since the operator
  // arrived — a real transition, so a fresh run dwells briefly on the watch beat rather than
  // leaping straight past it.
  const baselineSimTimeRef = useRef<string | null>(null);
  const [telemetryFlowing, setTelemetryFlowing] = useState(false);
  const simTime = runQuery.data?.simTime ?? null;
  useEffect(() => {
    if (!enabled) {
      baselineSimTimeRef.current = null;
      setTelemetryFlowing(false);
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
      setTelemetryFlowing(true);
    }
  }, [enabled, simTime]);

  const routeIncidentId = extractIncidentRouteId(pathname);
  // Entity ids are namespaced, so the selection tells us what kind of thing it is without
  // cross-referencing the incident list.
  const selectedIsIncident = selectedEntityId?.startsWith('incident:') ?? false;
  const incidentOpened =
    routeIncidentId != null || selectedIncidentId != null || selectedIsIncident;
  const assetSelected = selectedEntityId?.startsWith('asset:') ?? false;

  const incidents = incidentsQuery.data;
  const activeIncidentId =
    routeIncidentId ??
    selectedIncidentId ??
    (selectedIsIncident ? selectedEntityId : null) ??
    incidents?.[0]?.id ??
    null;

  const investigationQuery = useQuery({
    queryKey: queryKeys.incidents.investigation(activeIncidentId ?? ''),
    queryFn: ({ signal }) => client.getInvestigationDetail(activeIncidentId ?? '', signal),
    enabled: needsInvestigation && Boolean(activeIncidentId),
    refetchInterval: needsInvestigation ? POLL_INTERVAL_MS : false,
  });

  // The operator's own copilot threads. Tasks prove they asked; artifacts prove an agent
  // answered — two different beats, and on the local model minutes apart.
  const agentSessionsQuery = useRunAgentSessions(runId ?? '', 'operator', {
    enabled: needsAgents && Boolean(runId),
  });

  const reportEligible = runStatus ? REPORT_ELIGIBLE_RUN_STATUSES.has(runStatus) : false;
  const reportQuery = useQuery({
    queryKey: queryKeys.runs.afterActionReport(runId ?? ''),
    queryFn: ({ signal }) => client.getAfterActionReport(runId ?? '', signal),
    enabled: needsReport && reportEligible && Boolean(runId),
    refetchInterval: needsReport && reportEligible ? POLL_INTERVAL_MS : false,
  });

  const detail = investigationQuery.data;
  const proposalRaised = (detail?.proposals.length ?? 0) > 0;
  const operatorActionExecuted = (detail?.executedActions.length ?? 0) > 0;
  const containmentActionExecuted = detail
    ? detail.executedActions.some((action) => {
        const proposal = detail.proposals.find((candidate) => candidate.id === action.proposalId);
        if (!proposal) {
          return false;
        }
        const command = proposal.scenarioCommand ?? proposal.command;
        return !LOW_IMPACT_COMMANDS.has(command);
      })
    : false;
  const containmentResolved = detail
    ? detail.approvals.length > 0 ||
      detail.executedActions.length > 0 ||
      detail.proposals.some((proposal) => TERMINAL_PROPOSAL_STATUSES.has(proposal.status))
    : false;

  const sessions = agentSessionsQuery.data;
  const agentTaskCreated = sessions?.some((session) => session.tasks.length > 0) ?? false;
  const agentReplyReceived = sessions?.some((session) => session.artifacts.length > 0) ?? false;

  const alertRaised = (alertsQuery.data?.length ?? 0) > 0;
  const reportReady = reportEligible && reportQuery.isSuccess;

  const evidence: TutorialEvidence = useMemo(() => {
    if (!enabled) {
      return EMPTY_EVIDENCE;
    }
    return {
      welcomeAcknowledged: false,
      telemetryFlowing,
      assetSelected,
      graphOptionsOpened,
      alertRaised,
      incidentOpened,
      operatorActionExecuted,
      containmentActionExecuted,
      agentTaskCreated,
      agentReplyReceived,
      proposalRaised,
      containmentResolved,
      runComplete,
      reportReady,
    };
  }, [
    enabled,
    telemetryFlowing,
    assetSelected,
    graphOptionsOpened,
    alertRaised,
    incidentOpened,
    operatorActionExecuted,
    containmentActionExecuted,
    agentTaskCreated,
    agentReplyReceived,
    proposalRaised,
    containmentResolved,
    runComplete,
    reportReady,
  ]);

  return {
    scenarioVersionId: runQuery.data?.scenarioVersionId,
    // Reported straight from the query, not from `evidence` — the run clock has to be readable
    // even when the walkthrough is not observing anything, which is how the controller can
    // still tell the operator their run has ended.
    runStatus: runStatus ?? null,
    simTime,
    runReady: runQuery.isSuccess,
    evidence,
    activeIncidentId,
  };
}
