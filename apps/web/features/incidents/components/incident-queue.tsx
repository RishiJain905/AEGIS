'use client';

import Link from 'next/link';

import { EmptyState, ErrorState, LoadingState, MetricTile, cn, typographyTokens } from '@aegis/ui';

import { useIncidentQueue } from '../hooks/use-incident-queries';
import {
  formatRelativeAge,
  severityToRiskBand,
  summarizeQueue,
  type IncidentQueueRow,
} from '../lib/incident-model';
import { IncidentWorkspace } from './incident-workspace';
import { IncidentStateBadge, SEVERITY_ACCENT_BG, SeverityChip } from './incident-primitives';

function QueueRow({ row }: { row: IncidentQueueRow }) {
  const riskBand = severityToRiskBand(row.severity);
  return (
    <li className="border-b border-[var(--aegis-border-subtle)] last:border-b-0">
      <Link
        href={`/incidents/${encodeURIComponent(row.incident.id)}`}
        className="group relative flex flex-wrap items-center gap-x-4 gap-y-1.5 py-3 pl-5 pr-4 transition-colors duration-[var(--aegis-motion-duration-fast)] ease-[var(--aegis-motion-ease-standard)] hover:bg-[var(--aegis-surface-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--aegis-focus-ring)]"
        data-testid={`queue-row-${row.incident.id}`}
      >
        <span
          aria-hidden="true"
          className={cn(
            'absolute inset-y-0 left-0 w-[3px] opacity-70 transition-opacity duration-[var(--aegis-motion-duration-fast)] group-hover:opacity-100',
            SEVERITY_ACCENT_BG[riskBand],
          )}
        />
        <SeverityChip severity={row.severity} className="min-w-[4.75rem] shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-[var(--aegis-text-primary)] transition-colors group-hover:text-[var(--aegis-accent-strong)]">
            {row.incident.title}
          </span>
          <span className="mt-0.5 flex items-center gap-1.5 truncate font-[family-name:var(--aegis-font-mono)] text-[0.625rem] tracking-[0.02em] text-[var(--aegis-text-muted)]">
            <span className="truncate">{row.incident.id}</span>
            <span className="text-[var(--aegis-text-faint)]" aria-hidden="true">
              ·
            </span>
            <span className="truncate">{row.run.id}</span>
          </span>
        </span>
        <IncidentStateBadge state={row.incident.state} />
        <span className="w-16 text-right text-xs text-[var(--aegis-text-secondary)] tabular-nums">
          {row.linkedAlertCount} alert{row.linkedAlertCount === 1 ? '' : 's'}
        </span>
        <span className="w-12 text-right font-[family-name:var(--aegis-font-mono)] text-xs text-[var(--aegis-text-muted)] tabular-nums">
          {formatRelativeAge(row.incident.createdAt)}
        </span>
      </Link>
    </li>
  );
}

export function IncidentQueue() {
  const queueQuery = useIncidentQueue();

  return (
    <IncidentWorkspace
      eyebrow="Incident triage"
      title="Incident queue"
      description="Open cases across all active runs. Select an incident to manage its investigation and response."
    >
      {queueQuery.isPending ? (
        <LoadingState message="Loading incident queue…" data-testid="incident-queue-loading" />
      ) : queueQuery.isError ? (
        <ErrorState
          message="Unable to load incidents."
          onRetry={() => void queueQuery.refetch()}
          data-testid="incident-queue-error"
        />
      ) : queueQuery.data.length === 0 ? (
        <EmptyState
          title="No incidents"
          description="No incidents have been raised across active runs."
          data-testid="incident-queue-empty"
        />
      ) : (
        <>
          <QueueSummaryRow rows={queueQuery.data} />
          <section
            data-testid="incident-queue-list"
            aria-label="Open cases"
            className="relative overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)] before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[var(--aegis-border-highlight)]"
          >
            <header className="flex items-center justify-between gap-3 border-b border-[var(--aegis-border-subtle)] px-5 py-3.5">
              <h2 className={cn(typographyTokens.displayMd, 'text-[var(--aegis-text-primary)]')}>
                Open cases
              </h2>
              <span className={cn(typographyTokens.monoSm, 'text-[var(--aegis-text-muted)]')}>
                {queueQuery.data.length} total
              </span>
            </header>
            <ul className="flex flex-col" role="list">
              {queueQuery.data.map((row) => (
                <QueueRow key={row.incident.id} row={row} />
              ))}
            </ul>
          </section>
        </>
      )}
    </IncidentWorkspace>
  );
}

function QueueSummaryRow({ rows }: { rows: readonly IncidentQueueRow[] }) {
  const summary = summarizeQueue(rows);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="incident-queue-summary">
      <MetricTile label="Total incidents" value={summary.total} />
      <MetricTile label="Active" value={summary.active} />
      <MetricTile
        label="High / critical"
        value={summary.highSeverity}
        riskBand={summary.highSeverity > 0 ? 'high' : undefined}
      />
      <MetricTile label="Resolved" value={summary.resolved} />
    </div>
  );
}
