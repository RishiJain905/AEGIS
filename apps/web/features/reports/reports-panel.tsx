'use client';

import { useState } from 'react';

import type { AfterActionReportV1, ReportClaimV1 } from '@aegis/contracts-ts';
import { Badge, EmptyState, LoadingState, Panel } from '@aegis/ui';

import {
  CitationRef,
  ClaimTypeBadge,
  MetaRow,
  MonoChip,
  Pill,
  SectionLabel,
} from '@/features/reports/report-ui';
import { useAfterActionReport, useReportVersions } from '@/features/reports/use-report-queries';

export interface ReportsPanelProps {
  runId: string;
}

function Citations({ claim }: { claim: ReportClaimV1 }) {
  if (claim.citations.length === 0) {
    return null;
  }
  return (
    <ul className="mt-2 space-y-1">
      {claim.citations.map((citation) => (
        <li key={`${claim.claimId}-${citation.referenceId}`}>
          <CitationRef
            kind={citation.kind}
            referenceId={citation.referenceId}
            sequence={citation.sequence}
          />
        </li>
      ))}
    </ul>
  );
}

function ClaimCard({
  claim,
  selected,
  onSelect,
}: {
  claim: ReportClaimV1;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid={`report-claim-${claim.claimId}`}
      aria-pressed={selected}
      className={`w-full rounded-[var(--aegis-radius-md)] border px-3 py-2.5 text-left transition-colors duration-[var(--aegis-motion-duration-fast)] focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)] ${
        selected
          ? 'border-[var(--aegis-accent-line)] bg-[var(--aegis-surface-elevated)] shadow-[inset_2px_0_0_var(--aegis-accent-cyan)]'
          : 'border-[var(--aegis-border-subtle)] hover:border-[var(--aegis-border-default)] hover:bg-[var(--aegis-surface-hover)]'
      }`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <ClaimTypeBadge category={claim.category} />
        {!claim.grounded ? <Pill tone="warning">rejected</Pill> : null}
        {claim.confidence !== null && claim.confidence !== undefined ? (
          <Pill>{`${String(Math.round(claim.confidence * 100))}% conf`}</Pill>
        ) : null}
      </div>
      <p className="mt-2 line-clamp-3 text-sm leading-5 text-[var(--aegis-text-primary)]">
        {claim.text}
      </p>
    </button>
  );
}

function ReportContent({ report }: { report: AfterActionReportV1 }) {
  const [selectedClaimId, setSelectedClaimId] = useState(report.claims[0]?.claimId ?? '');

  const selectedClaim =
    report.claims.find((claim) => claim.claimId === selectedClaimId) ?? report.claims[0];

  return (
    <div className="space-y-5" data-testid="reports-panel">
      {/* Header / provenance */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge>{`v${String(report.versionNumber)}`}</Badge>
          <Pill tone="accent">immutable</Pill>
          {report.groundingFallback ? <Pill tone="warning">grounding fallback</Pill> : null}
          {report.narrativeProviderId ? <Pill>{report.narrativeProviderId}</Pill> : null}
        </div>
        {report.executiveSummary ? (
          <p className="text-sm leading-6 text-[var(--aegis-text-secondary)]">
            {report.executiveSummary}
          </p>
        ) : null}
        <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/50 px-3 py-1.5">
          <MetaRow label="Checksum">
            <MonoChip value={report.checksum} label="report checksum" variant="checksum" />
          </MetaRow>
          {report.sessionId ? (
            <MetaRow label="Session">
              <MonoChip value={report.sessionId} label="agent session id" />
            </MetaRow>
          ) : null}
          {report.taskId ? (
            <MetaRow label="Task">
              <MonoChip value={report.taskId} label="agent task id" />
            </MetaRow>
          ) : null}
        </div>
      </div>

      {/* Timeline */}
      {report.timeline.length > 0 ? (
        <div className="space-y-2">
          <SectionLabel count={report.timeline.length}>Timeline</SectionLabel>
          <ol className="max-h-44 space-y-1.5 overflow-y-auto pr-1">
            {report.timeline.map((entry) => (
              <li
                key={entry.eventId}
                data-testid={`report-timeline-${String(entry.sequence)}`}
                className="flex items-start gap-2 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/40 px-2 py-1.5"
              >
                <span className="mt-0.5 flex-none rounded bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-[0.65rem] leading-none text-[var(--aegis-text-muted)] tabular-nums">
                  {String(entry.sequence)}
                </span>
                <div className="min-w-0 flex-1">
                  <p
                    className="truncate text-xs text-[var(--aegis-text-primary)]"
                    title={entry.label}
                  >
                    {entry.label}
                  </p>
                  <MonoChip value={entry.eventId} label="event id" className="mt-1" />
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {/* Claims */}
      <div className="space-y-2">
        <SectionLabel count={report.claims.length}>Claims</SectionLabel>
        {report.claims.length === 0 ? (
          <p className="rounded-[var(--aegis-radius-md)] border border-dashed border-[var(--aegis-border-subtle)] px-3 py-4 text-center text-xs text-[var(--aegis-text-muted)]">
            No grounded claims recorded for this report.
          </p>
        ) : (
          <ul className="space-y-2">
            {report.claims.map((claim) => (
              <li key={claim.claimId}>
                <ClaimCard
                  claim={claim}
                  selected={claim.claimId === selectedClaim?.claimId}
                  onSelect={() => {
                    setSelectedClaimId(claim.claimId);
                  }}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Selected claim provenance */}
      {selectedClaim ? (
        <div className="space-y-2">
          <SectionLabel>Selected claim provenance</SectionLabel>
          <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)]/60 px-3 py-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <ClaimTypeBadge category={selectedClaim.category} />
              {!selectedClaim.grounded ? <Pill tone="warning">rejected</Pill> : null}
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--aegis-text-primary)]">
              {selectedClaim.text}
            </p>
            {selectedClaim.uncertainty ? (
              <p className="mt-2 text-xs italic leading-5 text-[var(--aegis-text-muted)]">
                Uncertainty: {selectedClaim.uncertainty}
              </p>
            ) : null}
            {selectedClaim.rejectionReason ? (
              <p className="mt-2 text-xs leading-5 text-[var(--aegis-status-suspicious)]">
                {selectedClaim.rejectionReason}
              </p>
            ) : null}
            {selectedClaim.citations.length > 0 ? (
              <div className="mt-3 border-t border-[var(--aegis-border-subtle)] pt-2">
                <span className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--aegis-text-muted)]">
                  Citations
                </span>
                <Citations claim={selectedClaim} />
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
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
      density="compact"
    >
      <ReportContent report={reportQuery.data} />
    </Panel>
  );
}
