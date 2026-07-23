'use client';

import type {
  CoachingLineV1,
  OperatorProfileMetricsV1,
  OperatorProfileV1,
} from '@aegis/contracts-ts';

import { useOperatorProfile } from './use-operator-profile';

const TONE_COLOR: Record<CoachingLineV1['tone'], string> = {
  reinforce: 'var(--aegis-status-positive, #34d399)',
  improve: 'var(--aegis-status-warning, #fbbf24)',
  neutral: 'var(--aegis-text-muted, #94a3b8)',
};

function formatEvents(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${String(Math.round(value))} evt`;
}

function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${String(Math.round(value * 100))}%`;
}

function StatRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--aegis-border-subtle)] py-1.5 last:border-b-0">
      <div className="flex flex-col">
        <span className="text-xs text-[var(--aegis-text-secondary)]">{label}</span>
        {hint && <span className="text-[10px] text-[var(--aegis-text-faint)]">{hint}</span>}
      </div>
      <span className="font-mono text-sm tabular-nums text-[var(--aegis-text-primary)]">
        {value}
      </span>
    </div>
  );
}

/** Compact inline score-trend sparkline. Purely decorative; the numeric avg is shown alongside. */
function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) {
    return null;
  }
  const width = 120;
  const height = 28;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const path = points
    .map((p, i) => {
      const x = i * step;
      const y = height - ((p - min) / span) * height;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg
      viewBox={`0 0 ${String(width)} ${String(height)}`}
      className="h-7 w-[120px]"
      role="img"
      aria-label={`Score trend across ${String(points.length)} runs`}
      preserveAspectRatio="none"
    >
      <path
        d={path}
        fill="none"
        stroke="var(--aegis-accent-cyan, #22d3ee)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Metrics({ metrics }: { metrics: OperatorProfileMetricsV1 }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-[var(--aegis-text-secondary)]">Score trend</span>
        <div className="flex items-center gap-2">
          <Sparkline points={metrics.scoreTrend} />
          <span className="font-mono text-sm tabular-nums text-[var(--aegis-text-primary)]">
            {formatPercent(metrics.avgScore)}
          </span>
        </div>
      </div>
      <StatRow
        label="Time to first triage"
        hint="events from first alert to first agent task"
        value={formatEvents(metrics.avgTimeToFirstTriage)}
      />
      <StatRow
        label="Containment latency"
        hint="events from first alert to first Class 2/3 action"
        value={formatEvents(metrics.avgContainmentLatency)}
      />
      <StatRow
        label="Over-containment"
        hint="aggressive actions on off-path assets"
        value={formatPercent(metrics.overContainmentRatio)}
      />
      <StatRow
        label="False-hypothesis rate"
        hint="hypotheses later refuted"
        value={formatPercent(metrics.falseHypothesisRate)}
      />
    </div>
  );
}

function Coaching({ lines }: { lines: CoachingLineV1[] }) {
  if (lines.length === 0) {
    return null;
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {lines.map((line) => (
        <li
          key={line.id}
          className="flex items-start gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2"
        >
          <span
            aria-hidden="true"
            className="mt-1.5 size-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: TONE_COLOR[line.tone] }}
          />
          <span className="text-xs leading-5 text-[var(--aegis-text-secondary)]">
            {line.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <section
      aria-labelledby="operator-profile-heading"
      className="flex flex-col gap-3 rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] p-4"
    >
      <div className="flex flex-col gap-0.5">
        <h3
          id="operator-profile-heading"
          className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]"
        >
          Your pattern
        </h3>
        <p className="text-[10px] text-[var(--aegis-text-faint)]">
          Deterministic cross-run telemetry from your own engagements — coaching, not scoring.
        </p>
      </div>
      {children}
    </section>
  );
}

/**
 * Presentational operator skill-telemetry panel: renders a resolved profile (or its empty
 * state). Pure — no data fetching — so it is trivially testable. Use {@link OperatorProfilePanel}
 * for the self-fetching version to mount in a page.
 */
export function OperatorProfilePanelView({ profile }: { profile: OperatorProfileV1 | null }) {
  if (!profile || profile.metrics.runsAnalyzed === 0) {
    return (
      <Frame>
        <p className="text-xs text-[var(--aegis-text-muted)]">
          No completed runs yet. Finish an engagement to start building your pattern.
        </p>
      </Frame>
    );
  }
  return (
    <Frame>
      <p className="font-mono text-[10px] text-[var(--aegis-text-faint)]">
        {profile.metrics.runsAnalyzed} run{profile.metrics.runsAnalyzed === 1 ? '' : 's'} analyzed
      </p>
      <Metrics metrics={profile.metrics} />
      <Coaching lines={profile.coaching} />
    </Frame>
  );
}

/**
 * Self-fetching operator skill-telemetry panel: a cross-run view of the caller's own speed,
 * bias, and containment discipline with deterministic coaching. Self-contained — mount anywhere.
 */
export function OperatorProfilePanel() {
  const query = useOperatorProfile();

  if (query.isLoading) {
    return (
      <Frame>
        <p className="text-xs text-[var(--aegis-text-muted)]" role="status">
          Loading your pattern…
        </p>
      </Frame>
    );
  }
  if (query.isError) {
    return (
      <Frame>
        <p className="text-xs text-[var(--aegis-status-danger,#f87171)]" role="alert">
          Could not load your operator profile.
        </p>
      </Frame>
    );
  }
  return <OperatorProfilePanelView profile={query.data ?? null} />;
}
