'use client';

import { useMemo, useState } from 'react';

import { EmptyState, ErrorState, LoadingState, Panel, cn } from '@aegis/ui';

import { useRunFeed, type RunFeedEntry } from '@/features/command-surface';
import { useRunGraph } from '@/features/shell/hooks/use-shell-queries';
import { useFocusAsset } from '@/features/operational-graph';

import { buildProposalFacts, describeAction, type ActionCardModel } from './action-model';
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

/** Stage → chip tone. Executed is the loud one; the rest report state without alarm. */
const STAGE_TONE: Record<string, string> = {
  executed: 'border-[var(--aegis-accent-line)] text-[var(--aegis-accent-strong)]',
  'awaiting approval':
    'border-[color-mix(in_srgb,var(--aegis-risk-medium)_60%,transparent)] text-[var(--aegis-risk-medium)]',
  blocked:
    'border-[color-mix(in_srgb,var(--aegis-risk-critical)_60%,transparent)] text-[var(--aegis-risk-critical)]',
  rejected:
    'border-[color-mix(in_srgb,var(--aegis-risk-high)_60%,transparent)] text-[var(--aegis-risk-high)]',
  cancelled: 'border-[var(--aegis-border-subtle)] text-[var(--aegis-text-muted)]',
  proposed: 'border-[var(--aegis-border-default)] text-[var(--aegis-text-secondary)]',
};

/** Stage → chip copy. Matches the action-result toast's vocabulary (BUG-012). */
const STAGE_LABEL: Record<string, string> = {
  executed: 'executed',
  'awaiting approval': 'awaiting approval',
  blocked: 'blocked by policy',
  rejected: 'rejected',
  cancelled: 'cancelled',
  proposed: 'proposed',
};

/**
 * A command order, rendered so it can be audited from the feed alone: what was done, to
 * which asset by name, at what class, under what policy verdict, with what effect and on
 * whose stated reason. The raw event stays one disclosure away for anyone who needs it.
 */
function ActionCard({
  entry,
  action,
  assetLabel,
  onFocusAsset,
}: {
  entry: RunFeedEntry;
  action: ActionCardModel;
  assetLabel: string | null;
  onFocusAsset: (assetId: string) => void;
}) {
  return (
    <li
      className="flex items-start gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2"
      data-testid="ops-feed-action"
      data-category={entry.category}
      data-stage={action.stage}
    >
      <span
        aria-hidden="true"
        className="mt-1 h-8 w-0.5 shrink-0 rounded-full"
        style={{ backgroundColor: 'var(--aegis-accent-cyan)' }}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              'rounded-full border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide',
              STAGE_TONE[action.stage] ?? STAGE_TONE['proposed'],
            )}
          >
            {STAGE_LABEL[action.stage] ?? action.stage}
          </span>
          {action.actionClassLabel ? (
            <span className="font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
              {action.actionClassLabel}
            </span>
          ) : null}
          <span className="ml-auto shrink-0 font-mono text-[10px] tabular-nums text-[var(--aegis-text-muted)]">
            {simTimeShort(entry.simTime)}
          </span>
        </div>

        <p className="flex flex-wrap items-baseline gap-1.5 text-[0.8125rem] leading-5 text-[var(--aegis-text-primary)]">
          <span className="font-medium">{action.verb}</span>
          {action.targetAssetId ? (
            <>
              <span className="text-[var(--aegis-text-muted)]">on</span>
              <button
                type="button"
                data-testid={`ops-feed-action-target-${entry.eventId}`}
                onClick={() => {
                  onFocusAsset(action.targetAssetId ?? '');
                }}
                className="rounded-[var(--aegis-radius-sm)] font-medium text-[var(--aegis-accent-strong)] underline decoration-[var(--aegis-accent-line)] underline-offset-2 transition-colors hover:text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
              >
                {assetLabel ?? action.targetAssetId}
              </button>
            </>
          ) : null}
        </p>

        {action.impact ? (
          <p className="text-[11px] leading-4 text-[var(--aegis-text-secondary)]">
            {action.impact}
            {action.reversible === false ? ' Not reversible.' : ''}
          </p>
        ) : null}

        {action.justification ? (
          <p className="border-l border-[var(--aegis-border-strong)] pl-2 text-[11px] italic leading-4 text-[var(--aegis-text-secondary)]">
            “{action.justification}”
          </p>
        ) : null}

        {action.policyOutcome ? (
          <span className="font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
            Policy: {action.policyOutcome.replace(/_/g, ' ')}
          </span>
        ) : null}

        <details className="mt-0.5">
          <summary className="cursor-pointer font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
            Raw event
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-base)] p-2 font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
            {entry.type}
            {'\n'}
            {JSON.stringify(entry.payload, null, 2)}
          </pre>
        </details>
      </div>
    </li>
  );
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

function FeedRowView({
  row,
  action,
  assetLabel,
  onFocusAsset,
}: {
  row: FeedRow;
  action: ActionCardModel | null;
  assetLabel: string | null;
  onFocusAsset: (assetId: string) => void;
}) {
  if (row.kind === 'collapsed') {
    return <CollapsedRow entries={row.entries} count={row.count} />;
  }
  if (action) {
    return (
      <ActionCard
        entry={row.entry}
        action={action}
        assetLabel={assetLabel}
        onFocusAsset={onFocusAsset}
      />
    );
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
  const graphQuery = useRunGraph(runId);
  const focusAsset = useFocusAsset();

  const entries = feedQuery.data ?? [];
  const rows = useMemo(() => buildFeedRows(entries), [entries]);
  const detection = useMemo(() => latestDetection(entries), [entries]);
  const proposalFacts = useMemo(() => buildProposalFacts(entries), [entries]);
  const assetLabels = useMemo(() => {
    const map = new Map<string, string>();
    for (const node of graphQuery.data?.snapshot?.nodes ?? []) {
      map.set(node.id, node.label);
    }
    return map;
  }, [graphQuery.data]);

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
            {rows.map((row) => {
              const action = row.kind === 'entry' ? describeAction(row.entry, proposalFacts) : null;
              return (
                <FeedRowView
                  key={row.key}
                  row={row}
                  action={action}
                  assetLabel={
                    action?.targetAssetId ? (assetLabels.get(action.targetAssetId) ?? null) : null
                  }
                  onFocusAsset={focusAsset}
                />
              );
            })}
          </ul>
        )}
      </div>
      <span className="sr-only" role="status" aria-live="assertive">
        {detection ? `Detection: ${detection.summary}` : ''}
      </span>
    </Panel>
  );
}
