'use client';

import { cn } from '@aegis/ui';

import type { IntentAssessment, IntentFinding, IntentFindingStatus } from './assess-intent';
import { useIntentReview } from './use-intent-review';

const STATUS_META: Record<
  IntentFindingStatus,
  { label: string; dot: string; text: string; border: string }
> = {
  held: {
    label: 'Held',
    dot: 'var(--aegis-accent-cyan, #22d3ee)',
    text: 'var(--aegis-status-positive, #34d399)',
    border: 'var(--aegis-status-positive, #34d399)',
  },
  tension: {
    label: 'Tension',
    dot: 'var(--aegis-status-warning, #fbbf24)',
    text: 'var(--aegis-status-warning, #fbbf24)',
    border: 'var(--aegis-status-warning, #fbbf24)',
  },
  violated: {
    label: 'Violated',
    dot: 'var(--aegis-status-danger, #f87171)',
    text: 'var(--aegis-status-danger, #f87171)',
    border: 'var(--aegis-status-danger, #f87171)',
  },
};

function StatusBadge({ status }: { status: IntentFindingStatus }) {
  const meta = STATUS_META[status];
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide"
      style={{ borderColor: meta.border, color: meta.text }}
    >
      <span
        aria-hidden="true"
        className="size-1.5 rounded-full"
        style={{ backgroundColor: meta.dot }}
      />
      {meta.label}
    </span>
  );
}

function FindingRow({ finding }: { finding: IntentFinding }) {
  return (
    <li className="flex flex-col gap-1 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
          {finding.title}
        </span>
        <StatusBadge status={finding.status} />
      </div>
      <p className="text-xs leading-5 text-[var(--aegis-text-muted)]">{finding.detail}</p>
      {finding.supportingEventIds.length > 0 && (
        <p className="font-mono text-[10px] text-[var(--aegis-text-faint)]">
          {finding.supportingEventIds.length} supporting event
          {finding.supportingEventIds.length === 1 ? '' : 's'}
        </p>
      )}
    </li>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <section
      aria-labelledby="intent-review-heading"
      className="flex flex-col gap-3 rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] p-4"
    >
      <div className="flex flex-col gap-0.5">
        <h3
          id="intent-review-heading"
          className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]"
        >
          Commander&apos;s intent review
        </h3>
        <p className="text-[10px] text-[var(--aegis-text-faint)]">
          Deterministic heuristics — your actions measured against the intent you set at launch.
        </p>
      </div>
      {children}
    </section>
  );
}

/**
 * After-action commander's-intent review. Restates the operator's launch intent and grades their
 * own action record against it as held / tension / violated findings. Fully deterministic (no
 * LLM) and self-contained: pass a terminated run's id.
 */
export function IntentReview({ runId }: { runId: string }) {
  const { sealed, intent, isLoading, isError, assessment } = useIntentReview(runId);

  if (!intent || intent.trim().length === 0) {
    return (
      <Frame>
        <p className="text-xs text-[var(--aegis-text-muted)]">
          No commander&apos;s intent was set for this run. Set one at launch to review your actions
          against your stated priorities.
        </p>
      </Frame>
    );
  }

  return (
    <Frame>
      <blockquote className="border-l-2 border-[var(--aegis-accent-line)] pl-3 text-sm italic text-[var(--aegis-text-primary)]">
        &ldquo;{intent}&rdquo;
      </blockquote>

      {!sealed && (
        <p className="text-xs text-[var(--aegis-text-muted)]">
          The intent review unlocks once the run ends.
        </p>
      )}

      {sealed && isLoading && (
        <p className="text-xs text-[var(--aegis-text-muted)]" role="status">
          Assembling intent review…
        </p>
      )}

      {sealed && isError && (
        <p className="text-xs text-[var(--aegis-status-danger,#f87171)]" role="alert">
          Could not load the run history for the intent review.
        </p>
      )}

      {sealed && !isLoading && !isError && assessment && <IntentFindings assessment={assessment} />}
    </Frame>
  );
}

function IntentFindings({ assessment }: { assessment: IntentAssessment }) {
  if (assessment.findings.length === 0) {
    return (
      <p className="text-xs text-[var(--aegis-text-muted)]">
        No intent-specific findings could be derived from this run&apos;s events
        {assessment.namedAssets.length === 0
          ? ' — the intent did not name assets the review could match.'
          : '.'}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      {assessment.namedAssets.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-text-faint)]">
            Named assets
          </span>
          {assessment.namedAssets.map((asset) => (
            <span
              key={asset.id}
              className={cn(
                'rounded-full border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)]',
                'px-2 py-0.5 font-mono text-[9px] text-[var(--aegis-text-secondary)]',
              )}
            >
              {asset.label}
            </span>
          ))}
        </div>
      )}
      <ul className="flex flex-col gap-2">
        {assessment.findings.map((finding) => (
          <FindingRow key={finding.id} finding={finding} />
        ))}
      </ul>
    </div>
  );
}
