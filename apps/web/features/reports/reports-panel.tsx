'use client';

import { useState } from 'react';

import type { AfterActionReportV1, ReportClaimV1 } from '@aegis/contracts-ts';
import { Badge, EmptyState, LoadingState, Panel } from '@aegis/ui';

import { useAfterActionReport, useReportVersions } from '@/features/reports/use-report-queries';

export interface ReportsPanelProps {
  runId: string;
}

function claimBadgeVariant(category: ReportClaimV1['category']): string {
  switch (category) {
    case 'observed_fact':
    case 'persisted_event':
    case 'investigation_evidence':
      return 'fact';
    case 'detection_score':
    case 'graph_risk':
      return 'score';
    case 'oracle_hypothesis':
    case 'bastion_proposal':
    case 'warden_policy_decision':
      return 'agent';
    case 'agent_inference':
    case 'uncertain':
      return 'inference';
    case 'unsupported':
    case 'human_decision':
      return 'unsupported';
    default: {
      const _exhaustive: never = category;
      throw new Error(`Unhandled claim category: ${String(_exhaustive)}`);
    }
  }
}

function ClaimDetail({ claim }: { claim: ReportClaimV1 }) {
  return (
    <div
      className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2"
      data-testid={`report-claim-${claim.claimId}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge data-claim-kind={claimBadgeVariant(claim.category)}>{claim.category}</Badge>
        {!claim.grounded ? <Badge>rejected</Badge> : null}
      </div>
      <p className="mt-2 text-sm">{claim.text}</p>
      {claim.rejectionReason ? (
        <p className="mt-2 text-xs text-[var(--aegis-text-secondary)]">{claim.rejectionReason}</p>
      ) : null}
      {claim.citations.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-[var(--aegis-text-secondary)]">
          {claim.citations.map((citation) => (
            <li key={`${claim.claimId}-${citation.referenceId}`}>
              <span className="font-medium text-[var(--aegis-text-primary)]">{citation.kind}</span>{' '}
              {citation.referenceId}
              {citation.sequence !== null && citation.sequence !== undefined
                ? ` · seq ${String(citation.sequence)}`
                : ''}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ReportContent({ report }: { report: AfterActionReportV1 }) {
  const [selectedClaimId, setSelectedClaimId] = useState(report.claims[0]?.claimId ?? '');

  const selectedClaim =
    report.claims.find((claim) => claim.claimId === selectedClaimId) ?? report.claims[0];

  return (
    <div className="space-y-4" data-testid="reports-panel">
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Badge>{`v${String(report.versionNumber)}`}</Badge>
          {report.groundingFallback ? <Badge>grounding fallback</Badge> : null}
          {report.narrativeProviderId ? <Badge>{report.narrativeProviderId}</Badge> : null}
        </div>
        <p className="text-sm">{report.executiveSummary}</p>
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          Checksum <code>{report.checksum}</code>
        </p>
        {report.sessionId ? (
          <p className="text-xs text-[var(--aegis-text-secondary)]">
            Session {report.sessionId} · Task {report.taskId}
          </p>
        ) : null}
      </div>

      <div>
        <h3 className="text-sm font-medium">Timeline</h3>
        <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs">
          {report.timeline.map((entry) => (
            <li key={entry.eventId} data-testid={`report-timeline-${String(entry.sequence)}`}>
              <span className="font-medium">{`seq ${String(entry.sequence)}`}</span> {entry.label}{' '}
              <code>{entry.eventId}</code>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Claims</h3>
          <ul className="space-y-2">
            {report.claims.map((claim) => (
              <li key={claim.claimId}>
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => {
                    setSelectedClaimId(claim.claimId);
                  }}
                >
                  <ClaimDetail claim={claim} />
                </button>
              </li>
            ))}
          </ul>
        </div>
        {selectedClaim ? (
          <div>
            <h3 className="text-sm font-medium">Selected claim provenance</h3>
            <div className="mt-2">
              <ClaimDetail claim={selectedClaim} />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ReportsPanel({ runId }: ReportsPanelProps) {
  const reportQuery = useAfterActionReport(runId);
  const versionsQuery = useReportVersions(runId);

  if (reportQuery.isError) {
    return (
      <EmptyState
        title="After-action report not ready"
        description="The report is generated after the run completes. Trigger SCRIBE once investigation, hypotheses, and proposals are available."
      />
    );
  }

  if (reportQuery.isPending || versionsQuery.isPending) {
    return <LoadingState message="Loading after-action report" />;
  }

  return (
    <Panel
      title="SCRIBE report"
      description={`${String(versionsQuery.data?.length ?? 0)} immutable version(s)`}
    >
      <ReportContent report={reportQuery.data} />
    </Panel>
  );
}
