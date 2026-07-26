'use client';

import { useMemo, useState } from 'react';

import { EmptyState, ErrorState, LoadingState, Panel, cn } from '@aegis/ui';

import { useRunFeed, type RunFeedEntry } from '@/features/command-surface';

import { buildFeedRows, latestDetection, type FeedRow } from './feed-model';

/** Category → short human label + accent token for the left rail + chip. */
const CATEGORY_META: Record<string, { label: string; accent: string }> = {
  agent: { label: 'Agent', accent: 'var(--aegis-accent)' },
  operator_action: { label: 'Operator', accent: 'var(--aegis-accent-cyan)' },
  roe: { label: 'RoE', accent: 'var(--aegis-accent-cyan)' },
  proposal: { label: 'Proposal', accent: 'var(--aegis-accent)' },
  policy: { label: 'Policy', accent: 'var(--aegis-text-muted)' },
  approval: { label: 'Approval', accent: 'var(--aegis-risk-medium)' },
  execution: { label: 'Executed', accent: 'var(--aegis-accent-cyan)' },
  incident: { label: 'Incident', accent: 'var(--aegis-risk-high)' },
  alert: { label: 'Alert', accent: 'var(--aegis-risk-high)' },
  reveal: { label: 'Detection', accent: 'var(--aegis-risk-critical)' },
  directive: { label: 'Directive', accent: 'var(--aegis-accent)' },
};

function categoryMeta(category: string): { label: string; accent: string } {
  return CATEGORY_META[category] ?? { label: category, accent: 'var(--aegis-text-muted)' };
}

function simTimeShort(simTime: string): string {
  // Show HH:MM:SS from an ISO timestamp; fall back to the raw value.
  const match = /T(\d{2}:\d{2}:\d{2})/.exec(simTime);
  return match?.[1] ?? simTime;
}

function InitiatorBadge({ initiator }: { initiator: string | null | undefined }) {
  if (initiator === 'operator') {
    return (
      <span className="rounded-full border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-accent-strong)]">
        Tasked
      </span>
    );
  }
  if (initiator === 'autonomy') {
    return (
      <span className="rounded-full border border-[var(--aegis-border-default)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-text-secondary)]">
        Autonomy
      </span>
    );
  }
  return null;
}

function EntryRow({
  entry,
  detection,
  biasCheck,
}: {
  entry: RunFeedEntry;
  detection: boolean;
  biasCheck: boolean;
}) {
  const meta = categoryMeta(entry.category);
  const biasBeat = biasCheck && !detection;
  return (
    <li
      className={cn(
        'flex items-start gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2',
        detection &&
          'border-[color-mix(in_srgb,var(--aegis-risk-critical)_60%,transparent)] bg-[color-mix(in_srgb,var(--aegis-risk-critical)_10%,var(--aegis-surface-raised))] shadow-[0_0_18px_-6px_var(--aegis-risk-critical)]',
        biasBeat &&
          'border-[color-mix(in_srgb,var(--aegis-risk-medium)_55%,transparent)] bg-[color-mix(in_srgb,var(--aegis-risk-medium)_9%,var(--aegis-surface-raised))]',
      )}
      data-testid={
        detection ? 'ops-feed-detection' : biasBeat ? 'ops-feed-bias-check' : 'ops-feed-entry'
      }
      data-category={entry.category}
    >
      <span
        aria-hidden="true"
        className="mt-1 h-8 w-0.5 shrink-0 rounded-full"
        style={{ backgroundColor: meta.accent }}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          {detection ? (
            <span className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-risk-critical)] px-1.5 py-0.5 font-[family-name:var(--aegis-font-display)] text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--aegis-surface-base)]">
              Detection
            </span>
          ) : biasBeat ? (
            <span className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-risk-medium)] px-1.5 py-0.5 font-[family-name:var(--aegis-font-display)] text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--aegis-surface-base)]">
              Bias check
            </span>
          ) : (
            <span
              className="rounded-[var(--aegis-radius-sm)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide"
              style={{ color: meta.accent }}
            >
              {meta.label}
            </span>
          )}
          {entry.category === 'agent' ? <InitiatorBadge initiator={entry.initiator} /> : null}
          <span className="ml-auto shrink-0 font-mono text-[10px] tabular-nums text-[var(--aegis-text-muted)]">
            {simTimeShort(entry.simTime)}
          </span>
        </div>
        <p
          className={cn(
            'break-words text-[0.8125rem] leading-5',
            detection
              ? 'font-medium text-[var(--aegis-text-primary)]'
              : 'text-[var(--aegis-text-secondary)]',
          )}
        >
          {entry.summary}
        </p>
      </div>
    </li>
  );
}

function CollapsedRow({ entries, count }: { entries: RunFeedEntry[]; count: number }) {
  const [open, setOpen] = useState(false);
  return (
    <li
      className="rounded-[var(--aegis-radius-md)] border border-dashed border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_55%,transparent)] px-3 py-2"
      data-testid="ops-feed-collapsed"
    >
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v);
        }}
        aria-expanded={open}
        className="flex w-full items-center gap-2 text-left"
      >
        <span aria-hidden="true" className="font-mono text-[10px] text-[var(--aegis-text-muted)]">
          {open ? '▾' : '▸'}
        </span>
        <span className="text-xs text-[var(--aegis-text-muted)]">
          {count} routine autonomy checks — no change
        </span>
      </button>
      {open ? (
        <ul className="mt-2 flex flex-col gap-1 border-t border-[var(--aegis-border-subtle)] pt-2">
          {entries.map((entry) => (
            <li
              key={entry.eventId}
              className="flex items-center gap-2 text-[11px] text-[var(--aegis-text-muted)]"
            >
              <span className="font-mono tabular-nums">{simTimeShort(entry.simTime)}</span>
              <span className="truncate">{entry.summary}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function FeedRowView({ row }: { row: FeedRow }) {
  if (row.kind === 'collapsed') {
    return <CollapsedRow entries={row.entries} count={row.count} />;
  }
  return <EntryRow entry={row.entry} detection={row.detection} biasCheck={row.biasCheck} />;
}

export interface OpsFeedPanelProps {
  runId: string;
}

/**
 * The ops feed — the command room's live heartbeat. A merged, newest-first stream of agent
 * findings (with operator-tasked vs autonomy initiator badges), proposals/approvals,
 * alerts/incidents, operator actions, RoE changes, and reveals rendered as loud DETECTION
 * beats. Routine autonomy no-change reports collapse so the feed keeps signal.
 */
export function OpsFeedPanel({ runId }: OpsFeedPanelProps) {
  const feedQuery = useRunFeed(runId);

  const entries = feedQuery.data ?? [];
  const rows = useMemo(() => buildFeedRows(entries), [entries]);
  const detection = useMemo(() => latestDetection(entries), [entries]);

  return (
    <Panel
      title="Ops feed"
      description="The room’s live heartbeat — findings, detections, and actions as they land."
      density="compact"
      data-testid="ops-feed-panel"
      className="min-h-0 flex-1"
    >
      <div
        className="flex h-full min-h-[8rem] flex-col gap-2 overflow-y-auto pr-1"
        aria-live="polite"
        aria-busy={feedQuery.isPending}
      >
        {feedQuery.isPending && entries.length === 0 ? (
          <LoadingState message="Tuning in to the run…" />
        ) : feedQuery.isError ? (
          <ErrorState
            title="Feed interrupted"
            message="The ops feed could not be reached."
            onRetry={() => void feedQuery.refetch()}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="Quiet on the floor"
            description="Agent findings, detections, and operator actions will stream in here as the run develops."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((row) => (
              <FeedRowView key={row.key} row={row} />
            ))}
          </ul>
        )}
      </div>
      <span className="sr-only" role="status" aria-live="assertive">
        {detection ? `Detection: ${detection.summary}` : ''}
      </span>
    </Panel>
  );
}
