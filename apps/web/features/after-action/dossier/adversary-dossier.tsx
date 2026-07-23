'use client';

import { type HTMLAttributes, type ReactNode } from 'react';

import { Badge, EmptyState, LoadingState, cn, typographyTokens } from '@aegis/ui';

import { Pill } from '@/features/reports/report-ui';
import { ApiClientError } from '@/lib/api/types';

import {
  formatDwell,
  secondsBetween,
  type AdversaryDossierViewModel,
  type DossierTimelineRow,
  type ExfilStatus,
} from './assemble-dossier';
import { useAdversaryDossier } from './use-dossier';

/* ------------------------------------------------------------------ */
/* Presentation primitives (kept local to the dossier feature)         */
/* ------------------------------------------------------------------ */

function Surface({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        'relative overflow-hidden rounded-[var(--aegis-radius-xl)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)]',
        'before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[var(--aegis-border-highlight)]',
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

function ZoneHeading({ children, count }: { children: ReactNode; count?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <h3
        className={cn(typographyTokens.displayMd, 'flex-none text-[var(--aegis-text-secondary)]')}
      >
        {children}
      </h3>
      {typeof count === 'number' ? (
        <span className="flex-none rounded-full bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-[0.65rem] leading-none text-[var(--aegis-text-muted)] tabular-nums">
          {count}
        </span>
      ) : null}
      <span className="h-px flex-1 bg-[var(--aegis-border-subtle)]" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Time helpers                                                        */
/* ------------------------------------------------------------------ */

function offsetLabel(startSimTime: string | undefined, simTime: string): string {
  if (!startSimTime) {
    return '';
  }
  const seconds = secondsBetween(startSimTime, simTime);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `+${String(h)}:${mm}:${ss}` : `+${mm}:${ss}`;
}

/* ------------------------------------------------------------------ */
/* Header dossier card                                                 */
/* ------------------------------------------------------------------ */

const EXFIL_TONE: Record<ExfilStatus, { pill: 'accent' | 'warning' | 'neutral'; ring: string }> = {
  contained: {
    pill: 'accent',
    ring: 'border-[var(--aegis-status-normal)]/40 bg-[var(--aegis-status-normal-bg)] text-[var(--aegis-status-normal)]',
  },
  detected_uncontained: {
    pill: 'warning',
    ring: 'border-[var(--aegis-status-suspicious)]/40 bg-[var(--aegis-status-suspicious-bg)] text-[var(--aegis-status-suspicious)]',
  },
  undetected: {
    pill: 'warning',
    ring: 'border-[var(--aegis-status-compromised)]/40 bg-[var(--aegis-status-compromised-bg)] text-[var(--aegis-status-compromised)]',
  },
};

function KeyMomentStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
        {label}
      </span>
      <span className="font-mono text-lg font-semibold tabular-nums text-[var(--aegis-text-primary)]">
        {value}
      </span>
      {sub ? <span className="text-[0.7rem] text-[var(--aegis-text-muted)]">{sub}</span> : null}
    </div>
  );
}

function DossierHeader({ dossier }: { dossier: AdversaryDossierViewModel }) {
  const km = dossier.keyMoments;
  const exfil = EXFIL_TONE[dossier.exfilOutcome.status];
  const start = km.runStartSimTime;

  return (
    <Surface
      className="p-6 lg:p-7"
      data-testid="dossier-header"
      aria-label="Adversary dossier summary"
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-2">
            <span
              className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-status-compromised)]')}
            >
              Adversary dossier
            </span>
            <h2
              className="font-[family-name:var(--aegis-font-display)] text-2xl font-semibold tracking-[0.01em] text-[var(--aegis-text-primary)]"
              data-testid="dossier-root-cause"
            >
              {dossier.rootCauseKnown
                ? `Root cause: ${dossier.rootCauseLabel}`
                : dossier.rootCauseLabel}
            </h2>
            <p className="max-w-xl text-sm leading-6 text-[var(--aegis-text-secondary)]">
              What the attacker did while you were responding — reconstructed from the full event
              record now the operation has ended.
            </p>
          </div>
          <div
            className={cn(
              'flex flex-col items-end gap-1 rounded-[var(--aegis-radius-md)] border px-3 py-2',
              exfil.ring,
            )}
            data-testid="dossier-exfil-outcome"
          >
            <span className="text-[0.65rem] font-semibold uppercase tracking-[0.1em]">
              Breach outcome
            </span>
            <span className="text-base font-semibold">{dossier.exfilOutcome.label}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 border-t border-[var(--aegis-border-subtle)] pt-5 sm:grid-cols-3 lg:grid-cols-5">
          <KeyMomentStat
            label="First breach"
            value={km.firstBreachSimTime ? offsetLabel(start, km.firstBreachSimTime) : '—'}
          />
          <KeyMomentStat
            label="First detection"
            value={km.firstDetectionSimTime ? offsetLabel(start, km.firstDetectionSimTime) : '—'}
            sub={
              km.timeToDetectionSeconds !== undefined
                ? `blind ${formatDwell(km.timeToDetectionSeconds)}`
                : 'never detected'
            }
          />
          <KeyMomentStat
            label="Containment"
            value={km.containmentSimTime ? offsetLabel(start, km.containmentSimTime) : '—'}
          />
          <KeyMomentStat
            label="Operation end"
            value={km.runEndSimTime ? offsetLabel(start, km.runEndSimTime) : '—'}
          />
          <KeyMomentStat
            label="Total undetected dwell"
            value={formatDwell(km.totalUndetectedDwellSeconds)}
          />
        </div>

        {dossier.objectivesOutcome ? (
          <div className="flex flex-wrap items-center gap-2" data-testid="dossier-objectives">
            <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
              Objectives
            </span>
            <Pill tone={dossier.objectivesOutcome.passed ? 'accent' : 'warning'}>
              {dossier.objectivesOutcome.passed ? 'Passed' : 'Failed'}
            </Pill>
            <Badge>{`Grade ${dossier.objectivesOutcome.grade}`}</Badge>
            <span className="font-mono text-sm text-[var(--aegis-text-muted)] tabular-nums">
              {dossier.objectivesOutcome.overallPct}%
            </span>
          </div>
        ) : null}
      </div>
    </Surface>
  );
}

/* ------------------------------------------------------------------ */
/* Two-lane timeline                                                   */
/* ------------------------------------------------------------------ */

function TimelineRow({
  row,
  startSimTime,
}: {
  row: DossierTimelineRow;
  startSimTime: string | undefined;
}) {
  const offset = offsetLabel(startSimTime, row.simTime);

  if (row.side === 'crossing') {
    return (
      <li
        className="col-span-full flex items-center gap-3 py-2"
        data-testid="dossier-crossing"
        data-side="crossing"
      >
        <span className="h-px flex-1 bg-[var(--aegis-status-contained)]/40" />
        <span className="inline-flex items-center gap-2 rounded-full border border-[var(--aegis-status-contained)]/50 bg-[var(--aegis-status-contained-bg)] px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.08em] text-[var(--aegis-status-contained)]">
          <span className="size-1.5 rounded-full bg-[var(--aegis-status-contained)] motion-safe:animate-pulse" />
          Detected
          <span className="font-mono normal-case tracking-normal opacity-80">{offset}</span>
        </span>
        <span className="min-w-0 flex-1 truncate text-xs text-[var(--aegis-text-muted)]">
          {row.label}
          {row.detail ? ` · ${row.detail}` : ''}
        </span>
      </li>
    );
  }

  const isAttacker = row.side === 'attacker';
  return (
    <li
      className={cn(
        'flex py-1.5',
        isAttacker ? 'col-start-1 justify-end pr-4 text-right' : 'col-start-3 justify-start pl-4',
      )}
      data-testid={isAttacker ? 'dossier-attacker-row' : 'dossier-defender-row'}
      data-side={row.side}
    >
      <div
        className={cn(
          'flex max-w-[22rem] flex-col gap-1 rounded-[var(--aegis-radius-md)] border px-3 py-2',
          isAttacker
            ? 'border-[var(--aegis-status-compromised)]/30 bg-[var(--aegis-status-compromised-bg)]/50'
            : 'border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)]',
        )}
      >
        <div
          className={cn('flex items-center gap-2', isAttacker ? 'flex-row-reverse' : 'flex-row')}
        >
          <span className="font-mono text-[0.65rem] text-[var(--aegis-text-muted)] tabular-nums">
            {offset}
          </span>
          <span className="text-sm font-medium leading-5 text-[var(--aegis-text-primary)]">
            {row.label}
          </span>
        </div>
        {row.detail ? (
          <span
            className={cn(
              'text-[0.7rem]',
              isAttacker
                ? 'text-[var(--aegis-status-suspicious)]'
                : 'text-[var(--aegis-text-muted)]',
            )}
          >
            {row.detail}
          </span>
        ) : null}
      </div>
    </li>
  );
}

function TwoLaneTimeline({ dossier }: { dossier: AdversaryDossierViewModel }) {
  const start = dossier.keyMoments.runStartSimTime;
  return (
    <Surface className="p-5 lg:p-6" aria-label="Attacker and defender timeline">
      <div className="flex flex-col gap-4">
        <ZoneHeading count={dossier.timeline.length}>Campaign timeline</ZoneHeading>
        <div className="grid grid-cols-2 gap-2 text-[0.7rem] uppercase tracking-[0.08em]">
          <span className="text-[var(--aegis-status-compromised)]">Attacker</span>
          <span className="text-right text-[var(--aegis-accent-cyan)]">Defender</span>
        </div>
        {dossier.timeline.length === 0 ? (
          <EmptyState
            title="No reconstructable activity"
            description="This run produced no attacker beats or defender actions to reconstruct."
            data-testid="dossier-timeline-empty"
          />
        ) : (
          <ol
            className="relative grid grid-cols-[minmax(0,1fr)_1px_minmax(0,1fr)] gap-x-0 gap-y-0.5 before:absolute before:inset-y-0 before:left-1/2 before:w-px before:-translate-x-1/2 before:bg-[var(--aegis-border-default)]"
            data-testid="dossier-timeline"
            aria-label="Chronological attacker and defender events"
          >
            {dossier.timeline.map((row) => (
              <TimelineRow key={row.id} row={row} startSimTime={start} />
            ))}
          </ol>
        )}
      </div>
    </Surface>
  );
}

/* ------------------------------------------------------------------ */
/* Sealed (mid-run) state                                              */
/* ------------------------------------------------------------------ */

function SealedState({ runStatus }: { runStatus: string | undefined }) {
  return (
    <Surface className="p-8" data-testid="dossier-sealed" aria-label="Adversary dossier sealed">
      <div className="flex flex-col items-center gap-3 text-center">
        <span
          className="flex size-12 items-center justify-center rounded-full border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] text-xl"
          aria-hidden="true"
        >
          🔒
        </span>
        <h2 className="font-[family-name:var(--aegis-font-display)] text-xl font-semibold text-[var(--aegis-text-primary)]">
          The dossier seals until the operation ends
        </h2>
        <p className="max-w-md text-sm leading-6 text-[var(--aegis-text-secondary)]">
          Revealing the attacker&apos;s full campaign mid-run would lift the fog of war. Once this
          run reaches a terminal state, the adversary lane unlocks for debrief.
        </p>
        {runStatus ? <Pill>{`Run status: ${runStatus}`}</Pill> : null}
      </div>
    </Surface>
  );
}

/* ------------------------------------------------------------------ */
/* Entry point                                                         */
/* ------------------------------------------------------------------ */

export interface AdversaryDossierProps {
  runId: string;
}

export function AdversaryDossier({ runId }: AdversaryDossierProps) {
  const { sealed, runStatus, isLoading, isError, error, dossier } = useAdversaryDossier(runId);

  if (!sealed) {
    return <SealedState runStatus={runStatus} />;
  }

  if (isLoading) {
    return <LoadingState message="Reconstructing the adversary campaign" />;
  }

  if (isError) {
    const message =
      error instanceof ApiClientError
        ? `${error.code}: ${error.message}`
        : 'Failed to reconstruct the adversary campaign';
    return (
      <EmptyState title="Dossier unavailable" description={message} data-testid="dossier-error" />
    );
  }

  if (!dossier) {
    return (
      <EmptyState
        title="No campaign data"
        description="The event record for this run is empty."
        data-testid="dossier-empty"
      />
    );
  }

  return (
    <div className="flex flex-col gap-6" data-testid="adversary-dossier">
      <DossierHeader dossier={dossier} />
      <TwoLaneTimeline dossier={dossier} />
    </div>
  );
}
