'use client';

import Link from 'next/link';

import { EmptyState, ErrorState, LoadingState, MetricTile, Panel } from '@aegis/ui';

import { useIncidentQueue } from '../hooks/use-incident-queries';
import { formatRelativeAge, summarizeQueue, type IncidentQueueRow } from '../lib/incident-model';
import { IncidentWorkspace } from './incident-workspace';
import { IncidentStateBadge, SeverityChip } from './incident-primitives';

function QueueRow({ row }: { row: IncidentQueueRow }) {
  return (
    <li>
      <Link
        href={`/incidents/${encodeURIComponent(row.incident.id)}`}
        className="group flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] px-4 py-3 transition-colors hover:border-[var(--aegis-accent-line)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-accent-cyan)]"
        data-testid={`queue-row-${row.incident.id}`}
      >
        <SeverityChip severity={row.severity} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-[var(--aegis-text-primary)] group-hover:text-[var(--aegis-accent-strong)]">
            {row.incident.title}
          </span>
          <span className="block truncate font-mono text-[0.625rem] text-[var(--aegis-text-muted)]">
            {row.incident.id} · {row.run.id}
          </span>
        </span>
        <IncidentStateBadge state={row.incident.state} />
        <span className="w-16 text-right text-xs text-[var(--aegis-text-secondary)] tabular-nums">
          {row.linkedAlertCount} alert{row.linkedAlertCount === 1 ? '' : 's'}
        </span>
        <span className="w-12 text-right font-mono text-xs text-[var(--aegis-text-muted)] tabular-nums">
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
          <Panel title="Open cases" data-testid="incident-queue-list">
            <ul className="flex flex-col gap-2" role="list">
              {queueQuery.data.map((row) => (
                <QueueRow key={row.incident.id} row={row} />
              ))}
            </ul>
          </Panel>
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
      <MetricTile label="High / critical" value={summary.highSeverity} />
      <MetricTile label="Resolved" value={summary.resolved} />
    </div>
  );
}
