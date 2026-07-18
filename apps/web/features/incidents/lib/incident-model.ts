import { NodeStatus } from '@aegis/contracts-ts';
import type {
  ActionProposalV1,
  AlertV1,
  ApprovalV1,
  ExecutedActionV1,
  IncidentV1,
  InvestigationDetailV1,
  PolicyDecisionV1,
  RunV1,
} from '@aegis/contracts-ts';
import type { NodeStatusValue, RiskBand } from '@aegis/ui';

/**
 * Incident-centric view models. These are pure functions so the triage
 * workspace can be reasoned about (and unit-tested) without React or the API
 * client. The Active-run experience is graph-first; this layer instead shapes
 * incidents for a "manage and triage" surface.
 */

export type AgentRole = 'WATCHTOWER' | 'TRACE' | 'ORACLE' | 'BASTION' | 'WARDEN' | 'SCRIBE';

export type IncidentPhase = 'triage' | 'investigating' | 'containing' | 'resolved';

export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info';

const SEVERITY_RANK: Record<SeverityLevel, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
};

export function normalizeSeverity(value: string | undefined | null): SeverityLevel {
  const normalized = (value ?? '').toLowerCase();
  if (
    normalized === 'critical' ||
    normalized === 'high' ||
    normalized === 'medium' ||
    normalized === 'low' ||
    normalized === 'info'
  ) {
    return normalized;
  }
  return 'info';
}

export function severityToRiskBand(severity: SeverityLevel): RiskBand {
  switch (severity) {
    case 'critical':
      return 'critical';
    case 'high':
      return 'high';
    case 'medium':
      return 'medium';
    default:
      return 'low';
  }
}

/** Highest severity across a set of alerts, defaulting to `info` when empty. */
export function maxSeverity(alerts: readonly AlertV1[]): SeverityLevel {
  return alerts.reduce<SeverityLevel>((worst, alert) => {
    const current = normalizeSeverity(alert.severity);
    return SEVERITY_RANK[current] > SEVERITY_RANK[worst] ? current : worst;
  }, 'info');
}

export interface IncidentPhasePresentation {
  phase: IncidentPhase;
  label: string;
  nodeStatus: NodeStatusValue;
  isResolved: boolean;
}

const STATE_PRESENTATION: Record<IncidentV1['state'], IncidentPhasePresentation> = {
  open: {
    phase: 'triage',
    label: 'Open',
    nodeStatus: NodeStatus.SUSPICIOUS,
    isResolved: false,
  },
  triaged: {
    phase: 'triage',
    label: 'Triaged',
    nodeStatus: NodeStatus.SUSPICIOUS,
    isResolved: false,
  },
  investigating: {
    phase: 'investigating',
    label: 'Investigating',
    nodeStatus: NodeStatus.UNDER_INVESTIGATION,
    isResolved: false,
  },
  containment_proposed: {
    phase: 'investigating',
    label: 'Containment proposed',
    nodeStatus: NodeStatus.UNDER_INVESTIGATION,
    isResolved: false,
  },
  approval_pending: {
    phase: 'investigating',
    label: 'Approval pending',
    nodeStatus: NodeStatus.UNDER_INVESTIGATION,
    isResolved: false,
  },
  containing: {
    phase: 'containing',
    label: 'Containing',
    nodeStatus: NodeStatus.CONTAINED,
    isResolved: false,
  },
  monitoring: {
    phase: 'containing',
    label: 'Monitoring',
    nodeStatus: NodeStatus.CONTAINED,
    isResolved: false,
  },
  resolved: {
    phase: 'resolved',
    label: 'Resolved',
    nodeStatus: NodeStatus.NORMAL,
    isResolved: true,
  },
  closed: {
    phase: 'resolved',
    label: 'Closed',
    nodeStatus: NodeStatus.NORMAL,
    isResolved: true,
  },
};

export function getIncidentStatePresentation(
  state: IncidentV1['state'],
): IncidentPhasePresentation {
  return STATE_PRESENTATION[state];
}

/** Short one-line description of the operator's next triage action. */
export function getNextAction(state: IncidentV1['state']): string {
  switch (state) {
    case 'open':
      return 'Triage linked alerts and confirm scope.';
    case 'triaged':
      return 'Launch investigation to gather evidence.';
    case 'investigating':
      return 'Review evidence and agent hypotheses as they arrive.';
    case 'containment_proposed':
      return 'Assess the proposed containment action.';
    case 'approval_pending':
      return 'Approve or reject the pending containment proposal.';
    case 'containing':
      return 'Monitor containment execution and dependency health.';
    case 'monitoring':
      return 'Confirm stability before resolving the incident.';
    case 'resolved':
    case 'closed':
      return 'Review the SCRIBE after-action report.';
    default:
      return 'Review incident status.';
  }
}

export interface IncidentQueueRow {
  incident: IncidentV1;
  run: RunV1;
  severity: SeverityLevel;
  linkedAlertCount: number;
  presentation: IncidentPhasePresentation;
}

export interface RunIncidentBundle {
  run: RunV1;
  incidents: readonly IncidentV1[];
  alerts: readonly AlertV1[];
}

/**
 * Flatten per-run incident data into a single triage queue, worst-first:
 * unresolved before resolved, then by severity, then oldest-open first.
 */
export function buildIncidentQueue(bundles: readonly RunIncidentBundle[]): IncidentQueueRow[] {
  const rows: IncidentQueueRow[] = [];
  for (const bundle of bundles) {
    const alertsById = new Map(bundle.alerts.map((alert) => [alert.id, alert]));
    for (const incident of bundle.incidents) {
      const linkedAlerts = incident.alertIds
        .map((id) => alertsById.get(id))
        .filter((alert): alert is AlertV1 => Boolean(alert));
      rows.push({
        incident,
        run: bundle.run,
        severity: maxSeverity(linkedAlerts),
        linkedAlertCount: incident.alertIds.length,
        presentation: getIncidentStatePresentation(incident.state),
      });
    }
  }

  return rows.sort((a, b) => {
    if (a.presentation.isResolved !== b.presentation.isResolved) {
      return a.presentation.isResolved ? 1 : -1;
    }
    const severityDelta = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity];
    if (severityDelta !== 0) {
      return severityDelta;
    }
    return a.incident.createdAt.localeCompare(b.incident.createdAt);
  });
}

export interface QueueSummary {
  total: number;
  active: number;
  resolved: number;
  highSeverity: number;
}

export function summarizeQueue(rows: readonly IncidentQueueRow[]): QueueSummary {
  return rows.reduce<QueueSummary>(
    (summary, row) => {
      summary.total += 1;
      if (row.presentation.isResolved) {
        summary.resolved += 1;
      } else {
        summary.active += 1;
      }
      if (row.severity === 'critical' || row.severity === 'high') {
        summary.highSeverity += 1;
      }
      return summary;
    },
    { total: 0, active: 0, resolved: 0, highSeverity: 0 },
  );
}

export type TriageEventTone = 'info' | 'watch' | 'danger' | 'success';

export interface TriageEvent {
  id: string;
  kind:
    | 'alert'
    | 'incident_opened'
    | 'triage'
    | 'investigation'
    | 'hypothesis'
    | 'proposal'
    | 'policy'
    | 'approval'
    | 'execution'
    | 'resolution';
  title: string;
  detail?: string;
  role?: AgentRole;
  timestamp: string;
  tone: TriageEventTone;
}

/**
 * Assemble a chronological triage narrative: alert raised -> incident opened ->
 * investigation -> proposals -> approvals -> resolution. Investigation detail is
 * optional; incidents without one still get the alert/open/state spine.
 */
export function buildTriageTimeline(
  incident: IncidentV1,
  linkedAlerts: readonly AlertV1[],
  investigation: InvestigationDetailV1 | null | undefined,
): TriageEvent[] {
  const events: TriageEvent[] = [];

  for (const alert of linkedAlerts) {
    events.push({
      id: `alert:${alert.id}`,
      kind: 'alert',
      title: `Alert raised — ${alert.title}`,
      detail: `${normalizeSeverity(alert.severity).toUpperCase()} · ${alert.assetId}`,
      timestamp: alert.createdAt,
      tone: 'danger',
    });
  }

  events.push({
    id: `incident_opened:${incident.id}`,
    kind: 'incident_opened',
    title: 'Incident opened',
    detail: incident.title,
    timestamp: incident.createdAt,
    tone: 'watch',
  });

  if (investigation) {
    for (const triage of investigation.triageResults) {
      events.push({
        id: `triage:${triage.id}`,
        kind: 'triage',
        title: `Triage — escalated to ${triage.escalation}`,
        detail: triage.escalationRationale,
        role: 'WATCHTOWER',
        timestamp: triage.createdAt,
        tone: 'watch',
      });
    }

    for (const plan of investigation.plans) {
      events.push({
        id: `plan:${plan.id}`,
        kind: 'investigation',
        title: 'Investigation plan created',
        detail: plan.rationale,
        role: 'TRACE',
        timestamp: plan.createdAt,
        tone: 'info',
      });
    }

    for (const revision of investigation.hypothesisRevisions) {
      events.push({
        id: `hypothesis:${revision.id}`,
        kind: 'hypothesis',
        title: `Hypothesis — ${revision.claim}`.slice(0, 140),
        detail: `${revision.family} family (confidence ${revision.confidence.point.toFixed(2)})`,
        role: 'ORACLE',
        timestamp: revision.createdAt,
        tone: 'info',
      });
    }

    for (const proposal of investigation.proposals) {
      events.push({
        id: `proposal:${proposal.id}`,
        kind: 'proposal',
        title: `Proposal — ${proposal.command} (${proposal.actionClass.replace('_', ' ')})`,
        detail: proposal.rationale || proposal.targetAssetId,
        role: 'BASTION',
        timestamp: proposal.createdAt,
        tone: 'watch',
      });
    }

    for (const decision of investigation.policyDecisions) {
      events.push({
        id: `policy:${decision.id}`,
        kind: 'policy',
        title: `Policy — ${decision.outcome.replace(/_/g, ' ')}`,
        detail: decision.explanationProse || decision.reasonCodes.join(', '),
        role: 'WARDEN',
        timestamp: decision.evaluatedAt,
        tone: decision.outcome === 'block' ? 'danger' : 'info',
      });
    }

    for (const approval of investigation.approvals) {
      events.push({
        id: `approval:${approval.id}`,
        kind: 'approval',
        title: `Human ${approval.decision} proposal`,
        detail: `By ${approval.approverId}`,
        timestamp: approval.decidedAt,
        tone: approval.decision === 'approved' ? 'success' : 'danger',
      });
    }

    for (const action of investigation.executedActions) {
      events.push({
        id: `execution:${action.id}`,
        kind: 'execution',
        title: 'Action executed',
        detail: action.proposalId,
        timestamp: action.executedAt,
        tone: 'success',
      });
    }
  }

  if (getIncidentStatePresentation(incident.state).isResolved) {
    events.push({
      id: `resolution:${incident.id}`,
      kind: 'resolution',
      title: `Incident ${getIncidentStatePresentation(incident.state).label.toLowerCase()}`,
      timestamp: incident.updatedAt,
      tone: 'success',
    });
  }

  return events.sort((a, b) => {
    const byTime = a.timestamp.localeCompare(b.timestamp);
    return byTime !== 0 ? byTime : a.id.localeCompare(b.id);
  });
}

export interface AgentActivity {
  role: AgentRole;
  present: boolean;
  headline: string;
  metricLabel: string;
  metricValue: number;
}

/**
 * Derive per-role agent participation directly from the investigation detail,
 * so every role in the pipeline is attributable to real persisted artifacts
 * (no dependence on which agent-session fixtures happen to exist).
 */
export function buildAgentRoster(
  investigation: InvestigationDetailV1 | null | undefined,
): AgentActivity[] {
  const triageCount = investigation?.triageResults.length ?? 0;
  const evidenceCount = investigation?.evidenceAttachments.length ?? 0;
  const planCount = investigation?.plans.length ?? 0;
  const hypothesisCount = investigation?.hypotheses.length ?? 0;
  const proposalCount = investigation?.proposals.length ?? 0;
  const pendingProposals =
    investigation?.proposals.filter((proposal) => proposal.status === 'pending').length ?? 0;
  const policyCount = investigation?.policyDecisions.length ?? 0;

  return [
    {
      role: 'WATCHTOWER',
      present: triageCount > 0,
      headline: triageCount > 0 ? 'Correlated alerts and set escalation.' : 'No triage recorded.',
      metricLabel: 'Triage results',
      metricValue: triageCount,
    },
    {
      role: 'TRACE',
      present: planCount > 0 || evidenceCount > 0,
      headline:
        planCount > 0 || evidenceCount > 0
          ? 'Expanded the graph and collected evidence.'
          : 'No investigation activity.',
      metricLabel: 'Evidence items',
      metricValue: evidenceCount,
    },
    {
      role: 'ORACLE',
      present: hypothesisCount > 0,
      headline:
        hypothesisCount > 0 ? 'Generated and compared hypotheses.' : 'No hypotheses generated.',
      metricLabel: 'Hypotheses',
      metricValue: hypothesisCount,
    },
    {
      role: 'BASTION',
      present: proposalCount > 0,
      headline:
        proposalCount > 0
          ? `Proposed ${String(proposalCount)} action${proposalCount === 1 ? '' : 's'} (${String(pendingProposals)} pending).`
          : 'No response proposed.',
      metricLabel: 'Proposals',
      metricValue: proposalCount,
    },
    {
      role: 'WARDEN',
      present: policyCount > 0,
      headline:
        policyCount > 0 ? 'Evaluated proposals against policy.' : 'No policy evaluation yet.',
      metricLabel: 'Policy decisions',
      metricValue: policyCount,
    },
  ];
}

export interface ProposalView {
  proposal: ActionProposalV1;
  policy: PolicyDecisionV1 | null;
  approval: ApprovalV1 | null;
  executed: ExecutedActionV1 | null;
}

/** Join each proposal to its latest policy decision, approval, and execution. */
export function buildProposalViews(
  investigation: InvestigationDetailV1 | null | undefined,
): ProposalView[] {
  if (!investigation) {
    return [];
  }
  return investigation.proposals.map((proposal) => ({
    proposal,
    policy:
      investigation.policyDecisions.find((decision) => decision.proposalId === proposal.id) ?? null,
    approval:
      investigation.approvals.find((approval) => approval.proposalId === proposal.id) ?? null,
    executed:
      investigation.executedActions.find((action) => action.proposalId === proposal.id) ?? null,
  }));
}

export function countPendingProposals(views: readonly ProposalView[]): number {
  return views.filter((view) => view.proposal.status === 'pending').length;
}

/** Compact relative age like `18d`, `3h`, `12m`, or `just now`. */
export function formatRelativeAge(iso: string, now: number = Date.now()): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) {
    return 'unknown';
  }
  const seconds = Math.max(0, Math.floor((now - then) / 1000));
  if (seconds < 60) {
    return 'just now';
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${String(minutes)}m`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${String(hours)}h`;
  }
  const days = Math.floor(hours / 24);
  return `${String(days)}d`;
}
