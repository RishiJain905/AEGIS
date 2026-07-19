'use client';

import { useCallback, useMemo, useState } from 'react';

import type {
  AfterActionReportV1,
  ReportClaimV1,
  ReportGenerationStatusV1,
  ReportTimelineEntryV1,
  ReportVersionV1,
} from '@aegis/contracts-ts';
import { Badge, Button, EmptyState, LoadingState, Panel, cn } from '@aegis/ui';

import {
  ClaimTypeBadge,
  MetaRow,
  MonoChip,
  Pill,
  SectionLabel,
} from '@/features/reports/report-ui';
import { useAfterActionReport, useReportVersions } from '@/features/reports/use-report-queries';

export interface ReportsWorkspaceProps {
  runId: string;
}

const STATUS_LABEL: Record<ReportGenerationStatusV1, string> = {
  completed: 'Completed',
  grounding_fallback: 'Grounding fallback',
  failed: 'Failed',
};

function StatusPill({ status }: { status: ReportGenerationStatusV1 }) {
  const tone =
    status === 'completed' ? 'accent' : status === 'grounding_fallback' ? 'warning' : 'neutral';
  return <Pill tone={tone}>{STATUS_LABEL[status]}</Pill>;
}

/* ------------------------------------------------------------------ */
/* Versions list                                                       */
/* ------------------------------------------------------------------ */

function VersionRow({
  version,
  isCurrent,
  selected,
  onSelect,
}: {
  version: ReportVersionV1;
  isCurrent: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      data-testid={`report-version-${String(version.versionNumber)}`}
      className={cn(
        'w-full rounded-[var(--aegis-radius-md)] border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)]',
        selected
          ? 'border-[var(--aegis-accent-line)] bg-[var(--aegis-surface-elevated)]'
          : 'border-[var(--aegis-border-subtle)] hover:border-[var(--aegis-border-default)] hover:bg-[var(--aegis-surface-hover)]',
      )}
    >
      <div className="flex items-center gap-2">
        <Badge>{`v${String(version.versionNumber)}`}</Badge>
        {isCurrent ? <Pill tone="accent">current</Pill> : null}
        <StatusPill status={version.status} />
      </div>
      <div className="mt-2 flex items-center gap-2">
        <MonoChip value={version.checksum} label="version checksum" variant="checksum" />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.7rem] text-[var(--aegis-text-muted)]">
        {version.providerId ? <span>{version.providerId}</span> : null}
        <span className="font-mono tabular-nums">
          seq {version.sourceSequenceFrom}–{version.sourceSequenceTo}
        </span>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Claim card (wide)                                                   */
/* ------------------------------------------------------------------ */

function ClaimCard({ claim }: { claim: ReportClaimV1 }) {
  return (
    <div
      data-testid={`report-claim-${claim.claimId}`}
      className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/40 px-3 py-3"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <ClaimTypeBadge category={claim.category} />
        {!claim.grounded ? <Pill tone="warning">rejected</Pill> : null}
        {claim.confidence !== null && claim.confidence !== undefined ? (
          <Pill>{`${String(Math.round(claim.confidence * 100))}% conf`}</Pill>
        ) : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-[var(--aegis-text-primary)]">{claim.text}</p>
      {claim.rejectionReason ? (
        <p className="mt-2 text-xs leading-5 text-[var(--aegis-status-suspicious)]">
          {claim.rejectionReason}
        </p>
      ) : null}
      {claim.citations.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-[var(--aegis-border-subtle)] pt-2">
          {claim.citations.map((citation) => (
            <span
              key={`${claim.claimId}-${citation.referenceId}`}
              className="inline-flex items-center gap-1"
            >
              <span className="rounded bg-[var(--aegis-surface-raised)] px-1 py-0.5 text-[0.62rem] font-medium uppercase tracking-[0.04em] text-[var(--aegis-text-secondary)]">
                {citation.kind}
              </span>
              <MonoChip value={citation.referenceId} label="citation reference" copyable={false} />
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TimelineList({ timeline }: { timeline: readonly ReportTimelineEntryV1[] }) {
  return (
    <ol className="space-y-1.5">
      {timeline.map((entry) => (
        <li
          key={entry.eventId}
          className="flex items-start gap-2 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/40 px-2.5 py-1.5"
        >
          <span className="mt-0.5 flex-none rounded bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-[0.65rem] leading-none text-[var(--aegis-text-muted)] tabular-nums">
            {String(entry.sequence)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-[var(--aegis-text-primary)]" title={entry.label}>
              {entry.label}
            </p>
            <MonoChip value={entry.eventId} label="event id" className="mt-1" />
          </div>
        </li>
      ))}
    </ol>
  );
}

function StringList({
  label,
  items,
  tone,
}: {
  label: string;
  items: readonly string[];
  tone: 'accent' | 'warning' | 'neutral';
}) {
  if (items.length === 0) {
    return null;
  }
  const dot =
    tone === 'warning'
      ? 'bg-[var(--aegis-status-suspicious)]'
      : tone === 'accent'
        ? 'bg-[var(--aegis-accent-cyan)]'
        : 'bg-[var(--aegis-text-muted)]';
  return (
    <div className="space-y-2">
      <SectionLabel count={items.length}>{label}</SectionLabel>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li
            key={item}
            className="flex gap-2 text-sm leading-5 text-[var(--aegis-text-secondary)]"
          >
            <span className={cn('mt-2 size-1 flex-none rounded-full', dot)} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Detail                                                              */
/* ------------------------------------------------------------------ */

function CurrentReportDetail({ report }: { report: AfterActionReportV1 }) {
  return (
    <div className="space-y-5" data-testid="reports-detail">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{`v${String(report.versionNumber)}`}</Badge>
          <Pill tone="accent">immutable</Pill>
          {report.groundingFallback ? <Pill tone="warning">grounding fallback</Pill> : null}
          {report.narrativeProviderId ? <Pill>{report.narrativeProviderId}</Pill> : null}
        </div>
        {report.title ? (
          <h2 className="font-[family-name:var(--aegis-font-display)] text-lg font-semibold text-[var(--aegis-text-primary)]">
            {report.title}
          </h2>
        ) : null}
        <p className="text-sm leading-6 text-[var(--aegis-text-secondary)]">
          {report.executiveSummary}
        </p>
        <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/50 px-3 py-1.5">
          <MetaRow label="Checksum">
            <MonoChip value={report.checksum} label="report checksum" variant="checksum" />
          </MetaRow>
          {report.createdAt ? (
            <MetaRow label="Created">
              <span
                className="font-mono text-[0.7rem] text-[var(--aegis-text-secondary)]"
                title={report.createdAt}
              >
                {report.createdAt}
              </span>
            </MetaRow>
          ) : null}
          {report.sessionId ? (
            <MetaRow label="Session">
              <MonoChip value={report.sessionId} label="agent session id" />
            </MetaRow>
          ) : null}
        </div>
      </div>

      {report.chronologySummary ? (
        <div className="space-y-2">
          <SectionLabel>Chronology</SectionLabel>
          <p className="text-sm leading-6 text-[var(--aegis-text-secondary)]">
            {report.chronologySummary}
          </p>
        </div>
      ) : null}

      {report.claims.length > 0 ? (
        <div className="space-y-2">
          <SectionLabel count={report.claims.length}>Grounded claims</SectionLabel>
          <div className="grid gap-2 md:grid-cols-2">
            {report.claims.map((claim) => (
              <ClaimCard key={claim.claimId} claim={claim} />
            ))}
          </div>
        </div>
      ) : null}

      {report.timeline.length > 0 ? (
        <div className="space-y-2">
          <SectionLabel count={report.timeline.length}>Timeline</SectionLabel>
          <TimelineList timeline={report.timeline} />
        </div>
      ) : null}

      <StringList label="Lessons" items={report.lessons} tone="accent" />
      <StringList label="Uncertainties" items={report.uncertainties} tone="warning" />
      <StringList label="Contradictions" items={report.contradictions} tone="warning" />
    </div>
  );
}

function ArchivedVersionDetail({ version }: { version: ReportVersionV1 }) {
  return (
    <div className="space-y-4" data-testid="reports-detail">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{`v${String(version.versionNumber)}`}</Badge>
        <Pill tone="accent">immutable</Pill>
        <StatusPill status={version.status} />
      </div>
      <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/50 px-3 py-1.5">
        <MetaRow label="Checksum">
          <MonoChip value={version.checksum} label="version checksum" variant="checksum" />
        </MetaRow>
        <MetaRow label="Report id">
          <MonoChip value={version.reportId} label="report id" />
        </MetaRow>
        {version.providerId ? (
          <MetaRow label="Provider">
            <span className="text-[0.7rem] text-[var(--aegis-text-secondary)]">
              {version.providerId}
            </span>
          </MetaRow>
        ) : null}
        <MetaRow label="Source seq">
          <span className="font-mono text-[0.7rem] text-[var(--aegis-text-secondary)] tabular-nums">
            {version.sourceSequenceFrom}–{version.sourceSequenceTo}
          </span>
        </MetaRow>
        <MetaRow label="Created">
          <span
            className="font-mono text-[0.7rem] text-[var(--aegis-text-secondary)]"
            title={version.createdAt}
          >
            {version.createdAt}
          </span>
        </MetaRow>
      </div>
      <p className="rounded-[var(--aegis-radius-md)] border border-dashed border-[var(--aegis-border-subtle)] px-3 py-4 text-center text-xs text-[var(--aegis-text-muted)]">
        This is an archived immutable version. Full claim and timeline rendering is shown for the
        current version.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Workspace                                                           */
/* ------------------------------------------------------------------ */

export function ReportsWorkspace({ runId }: ReportsWorkspaceProps) {
  const reportQuery = useAfterActionReport(runId);
  const versionsQuery = useReportVersions(runId);

  const report = reportQuery.data;
  const versions = useMemo(() => {
    const list = versionsQuery.data ?? [];
    return [...list].sort((a, b) => b.versionNumber - a.versionNumber);
  }, [versionsQuery.data]);

  const currentVersionNumber = report?.versionNumber ?? versions[0]?.versionNumber ?? null;
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const activeVersion = selectedVersion ?? currentVersionNumber;

  const handleExport = useCallback(() => {
    if (!report) {
      return;
    }
    try {
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `scribe-report-${report.runId}-v${String(report.versionNumber)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      /* download unavailable — ignore */
    }
  }, [report]);

  if (reportQuery.isError) {
    return (
      <EmptyState
        title="After-action report not ready"
        description="Reports are generated after the run completes. Trigger SCRIBE once investigation, hypotheses, and proposals are available."
        data-testid="reports-empty"
      />
    );
  }

  if (reportQuery.isPending || versionsQuery.isPending) {
    return <LoadingState message="Loading reports" />;
  }

  const selectedVersionMeta = versions.find((v) => v.versionNumber === activeVersion);
  const showCurrent = activeVersion === currentVersionNumber;

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6" data-testid="reports-workspace">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[var(--aegis-accent-cyan)]">
            SCRIBE
          </span>
          <h1 className="font-[family-name:var(--aegis-font-display)] text-2xl font-semibold tracking-[0.01em] text-[var(--aegis-text-primary)]">
            After-action reports
          </h1>
          <div className="flex items-center gap-2">
            <span className="text-[0.7rem] uppercase tracking-[0.06em] text-[var(--aegis-text-muted)]">
              Run
            </span>
            <MonoChip value={runId} label="run id" />
          </div>
        </div>
        <Button size="sm" variant="secondary" onClick={handleExport} data-testid="reports-export">
          Export JSON
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Panel
          title="Versions"
          description={`${String(versions.length)} immutable version(s)`}
          density="comfortable"
        >
          <div className="space-y-2" data-testid="report-versions-list">
            {versions.length === 0 ? (
              <p className="text-sm text-[var(--aegis-text-muted)]">No versions recorded.</p>
            ) : (
              versions.map((version) => (
                <VersionRow
                  key={version.id}
                  version={version}
                  isCurrent={version.versionNumber === currentVersionNumber}
                  selected={version.versionNumber === activeVersion}
                  onSelect={() => {
                    setSelectedVersion(version.versionNumber);
                  }}
                />
              ))
            )}
          </div>
        </Panel>

        <Panel title="Report" density="comfortable">
          {showCurrent && report ? (
            <CurrentReportDetail report={report} />
          ) : selectedVersionMeta ? (
            <ArchivedVersionDetail version={selectedVersionMeta} />
          ) : report ? (
            <CurrentReportDetail report={report} />
          ) : (
            <EmptyState
              title="No report selected"
              description="Select a version to view its detail."
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
