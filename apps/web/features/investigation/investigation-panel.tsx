'use client';

import type {
  AgentSessionDetailV1,
  EvidenceAttachmentV1,
  InvestigationDetailV1,
  WatchtowerTriageResultV1,
} from '@aegis/contracts-ts';
import { NodeStatus } from '@aegis/contracts-ts';
import { Alert, Badge, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';
import type { NodeStatusValue } from '@aegis/ui';

import { GraphHighlightMode } from '@/features/operational-graph/contracts/graph-visual-state';
import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';

import { useInvestigationAgentSessions, useInvestigationDetail } from './use-investigation-queries';

export interface InvestigationPanelProps {
  incidentId: string;
}

function escalationVariant(
  escalation: WatchtowerTriageResultV1['escalation'],
): 'info' | 'warning' | 'error' {
  switch (escalation) {
    case 'monitor':
      return 'info';
    case 'investigate':
      return 'warning';
    case 'urgent':
      return 'error';
    default: {
      const _exhaustive: never = escalation;
      throw new Error(`Unhandled escalation level: ${String(_exhaustive)}`);
    }
  }
}

function taskStatusBadge(status: string): NodeStatusValue {
  switch (status) {
    case 'completed':
      return NodeStatus.NORMAL;
    case 'running':
    case 'queued':
      return NodeStatus.UNDER_INVESTIGATION;
    case 'failed':
    case 'timed_out':
      return NodeStatus.COMPROMISED;
    case 'cancelled':
      return NodeStatus.SUSPICIOUS;
    default:
      return NodeStatus.SUSPICIOUS;
  }
}

function ProvenanceSummary({ attachment }: { attachment: EvidenceAttachmentV1 }) {
  const { provenance } = attachment;
  return (
    <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
      <div>
        <dt className="text-[var(--aegis-text-muted)]">Source</dt>
        <dd>
          {provenance.sourceType} · <span className="font-mono">{provenance.sourceId}</span>
        </dd>
      </div>
      {provenance.collectedByTool ? (
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Collected by</dt>
          <dd className="font-mono">{provenance.collectedByTool}</dd>
        </div>
      ) : null}
      {provenance.collectedAtSequence != null ? (
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Sequence</dt>
          <dd className="font-mono">{provenance.collectedAtSequence}</dd>
        </div>
      ) : null}
      <div className="col-span-2">
        <dt className="text-[var(--aegis-text-muted)]">Summary</dt>
        <dd>{provenance.summary}</dd>
      </div>
    </dl>
  );
}

function TriageSection({ triageResults }: { triageResults: WatchtowerTriageResultV1[] }) {
  if (triageResults.length === 0) {
    return null;
  }

  return (
    <Panel title="WATCHTOWER triage" density="compact" data-testid="investigation-triage-panel">
      <ul className="flex flex-col gap-3">
        {triageResults.map((triage) => (
          <li
            key={triage.id}
            className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2"
            data-testid={`triage-result-${triage.id}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge nodeStatus={taskStatusBadge('completed')}>{triage.escalation}</Badge>
              <span className="text-xs text-[var(--aegis-text-muted)]">
                {Math.round(triage.confidence * 100)}% confidence
              </span>
            </div>
            <Alert
              variant={escalationVariant(triage.escalation)}
              className="mt-2"
              title="Escalation"
            >
              {triage.escalationRationale}
            </Alert>
            {triage.correlationDecisions.length > 0 ? (
              <details className="mt-2 text-xs text-[var(--aegis-text-secondary)]">
                <summary className="cursor-pointer">Correlation decisions</summary>
                <ul className="mt-2 flex flex-col gap-2">
                  {triage.correlationDecisions.map((decision, index) => (
                    <li key={`${triage.id}-decision-${String(index)}`}>
                      <span className="font-medium">{decision.decision}</span>
                      <span className="ml-2 font-mono text-[10px]">
                        {decision.alertIds.join(', ')}
                      </span>
                      <p className="mt-1">{decision.rationale}</p>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function EvidenceSection({
  attachments,
  contradictions,
}: {
  attachments: EvidenceAttachmentV1[];
  contradictions: EvidenceAttachmentV1[];
}) {
  if (attachments.length === 0 && contradictions.length === 0) {
    return null;
  }

  return (
    <>
      {attachments.length > 0 ? (
        <Panel
          title="Evidence attachments"
          density="compact"
          data-testid="investigation-evidence-panel"
        >
          <ul className="flex flex-col gap-3">
            {attachments.map((attachment) => (
              <li
                key={attachment.id}
                className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-sm"
                data-testid={`evidence-attachment-${attachment.id}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{attachment.provenance.summary}</span>
                  <Badge>{Math.round(attachment.confidence * 100)}%</Badge>
                </div>
                <p className="mt-1 text-xs text-[var(--aegis-text-secondary)]">
                  {attachment.rationale}
                </p>
                <ProvenanceSummary attachment={attachment} />
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      {contradictions.length > 0 ? (
        <Panel
          title="Contradictions"
          density="compact"
          data-testid="investigation-contradictions-panel"
        >
          <ul className="flex flex-col gap-3">
            {contradictions.map((attachment) => (
              <li
                key={attachment.id}
                className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-status-suspicious)] bg-[var(--aegis-status-suspicious-bg)] px-3 py-2 text-sm"
                data-testid={`contradiction-${attachment.id}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge nodeStatus={NodeStatus.SUSPICIOUS}>Contradiction</Badge>
                  <span className="font-medium">{attachment.provenance.summary}</span>
                </div>
                <p className="mt-1 text-xs">{attachment.rationale}</p>
                <ProvenanceSummary attachment={attachment} />
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </>
  );
}

function AgentLifecycleSection({ sessions }: { sessions: AgentSessionDetailV1[] }) {
  if (sessions.length === 0) {
    return null;
  }

  return (
    <Panel
      title="Agent task lifecycle"
      density="compact"
      data-testid="investigation-agent-lifecycle-panel"
    >
      <ul className="flex flex-col gap-3">
        {sessions.map((detail) => (
          <li
            key={detail.session.id}
            className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2"
            data-testid={`agent-session-${detail.session.id}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{detail.session.role}</span>
              <Badge nodeStatus={taskStatusBadge(detail.session.state)}>
                {detail.session.state}
              </Badge>
            </div>
            <p className="mt-1 font-mono text-[10px] text-[var(--aegis-text-muted)]">
              {detail.session.id}
            </p>
            {detail.tasks.length > 0 ? (
              <ul className="mt-2 flex flex-col gap-1">
                {detail.tasks.map((task) => (
                  <li key={task.id} className="text-xs">
                    <span className="font-mono">{task.id}</span>
                    <Badge className="ml-2" nodeStatus={taskStatusBadge(task.status)}>
                      {task.status}
                    </Badge>
                    {task.attempt > 1 ? (
                      <span className="ml-2 text-[var(--aegis-text-muted)]">
                        attempt {task.attempt}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
            {detail.transitions.length > 0 ? (
              <details className="mt-2 text-xs text-[var(--aegis-text-secondary)]">
                <summary className="cursor-pointer">State transitions</summary>
                <ol className="mt-2 flex list-decimal flex-col gap-1 pl-4">
                  {detail.transitions.map((transition) => (
                    <li key={transition.id}>
                      {transition.fromState} → {transition.toState}
                      <span className="ml-2 text-[var(--aegis-text-muted)]">
                        {transition.reason}
                      </span>
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}
            {detail.toolInvocations.length > 0 ? (
              <details className="mt-2 text-xs text-[var(--aegis-text-secondary)]">
                <summary className="cursor-pointer">
                  Tool invocations ({detail.toolInvocations.length})
                </summary>
                <ul className="mt-2 flex flex-col gap-1">
                  {detail.toolInvocations.map((invocation) => (
                    <li key={invocation.id} className="font-mono text-[10px]">
                      {invocation.toolName} · {invocation.status}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function OverlayActions({ detail }: { detail: InvestigationDetailV1 }) {
  const setHighlight = useGraphVisualStore((state) => state.setHighlight);
  const latestOverlay = detail.overlays.at(-1);

  if (!latestOverlay) {
    return null;
  }

  const nodeIds = latestOverlay.highlights
    .filter((highlight) => highlight.entityType === 'asset')
    .map((highlight) => highlight.entityId);
  const edgeIds = latestOverlay.edgeHighlights.map((highlight) => highlight.entityId);

  return (
    <Panel title="Graph overlay" density="compact" data-testid="investigation-overlay-panel">
      <p className="text-xs text-[var(--aegis-text-secondary)]">{latestOverlay.rationale}</p>
      <p className="mt-2 text-xs text-[var(--aegis-text-muted)]">
        {nodeIds.length} nodes · {edgeIds.length} edges highlighted
      </p>
      <button
        type="button"
        className="mt-2 text-xs text-[var(--aegis-accent)] underline"
        data-testid="highlight-investigation-overlay"
        onClick={() => {
          setHighlight(GraphHighlightMode.INCIDENT, nodeIds, edgeIds, false);
        }}
      >
        Highlight TRACE overlay on graph
      </button>
    </Panel>
  );
}

function InvestigationContent({
  detail,
  sessions,
}: {
  detail: InvestigationDetailV1;
  sessions: AgentSessionDetailV1[];
}) {
  const supportingEvidence = detail.evidenceAttachments.filter(
    (attachment) => !attachment.isContradiction,
  );
  const contradictions = detail.evidenceAttachments.filter(
    (attachment) => attachment.isContradiction,
  );

  const hasContent =
    detail.triageResults.length > 0 ||
    supportingEvidence.length > 0 ||
    contradictions.length > 0 ||
    detail.notes.length > 0 ||
    sessions.length > 0 ||
    detail.overlays.length > 0;

  if (!hasContent) {
    return (
      <EmptyState
        title="No investigation artifacts"
        description="WATCHTOWER and TRACE outputs will appear here once triage and evidence collection complete."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <TriageSection triageResults={detail.triageResults} />
      <EvidenceSection attachments={supportingEvidence} contradictions={contradictions} />
      {detail.notes.length > 0 ? (
        <Panel
          title="Investigation notes"
          density="compact"
          data-testid="investigation-notes-panel"
        >
          <ul className="flex flex-col gap-2">
            {detail.notes.map((note) => (
              <li
                key={note.id}
                className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-sm"
                data-testid={`investigation-note-${note.id}`}
              >
                <p>{note.note}</p>
                <p className="mt-1 font-mono text-[10px] text-[var(--aegis-text-muted)]">
                  evidence: {note.evidenceIds.join(', ')}
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
      <AgentLifecycleSection sessions={sessions} />
      <OverlayActions detail={detail} />
    </div>
  );
}

export function InvestigationPanel({ incidentId }: InvestigationPanelProps) {
  const investigationQuery = useInvestigationDetail(incidentId);
  const agentSessionsQuery = useInvestigationAgentSessions(incidentId);

  if (investigationQuery.isPending || agentSessionsQuery.isPending) {
    return <LoadingState message="Loading investigation…" />;
  }

  if (investigationQuery.isError || agentSessionsQuery.isError) {
    return (
      <ErrorState
        message="Unable to load investigation detail."
        onRetry={() => {
          void investigationQuery.refetch();
          void agentSessionsQuery.refetch();
        }}
      />
    );
  }

  return (
    <div data-testid="investigation-panel">
      <InvestigationContent
        detail={investigationQuery.data}
        sessions={agentSessionsQuery.sessions}
      />
    </div>
  );
}
