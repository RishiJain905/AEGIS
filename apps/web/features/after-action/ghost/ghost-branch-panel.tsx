'use client';

/**
 * Ghost branch panel — the after-action counterfactual-replay surface.
 *
 * The operator picks one of their real decision points (an executed containment or an
 * "inaction window"), asks "what if I had done X instead / earlier / nothing?", and a
 * deterministic engine re-simulates and returns the REAL alternate timeline. This component
 * is presentation + form assembly only: all I/O lives in `use-ghost-branch.ts`.
 *
 * Fog-of-war gate: while the run is live the panel renders a compact sealed state and never
 * touches the ghost endpoints (the decision-points query only mounts once terminal).
 */

import { useMemo, useState, type HTMLAttributes, type ReactNode } from 'react';

import type {
  GhostBranchModeV1,
  GhostBranchRequestV1,
  GhostBranchResultV1,
  GhostDecisionPointV1,
  GhostOutcomeV1,
  ScenarioCommandTemplateV1,
} from '@aegis/contracts-ts';
import { EmptyState, LoadingState, MetricTile, cn, typographyTokens } from '@aegis/ui';

import { isTerminalRunStatus } from '@/features/after-action/dossier/use-dossier';
import { MonoChip, Pill } from '@/features/reports/report-ui';
import { useRun } from '@/features/shell/hooks/use-shell-queries';
import { ApiClientError } from '@/lib/api/types';

import { GhostTimeline } from './ghost-timeline';
import { useGhostDecisionPoints, useGhostRunMutation } from './use-ghost-branch';

/* ------------------------------------------------------------------ */
/* Presentation primitives (copied from the dossier so the two after-  */
/* action surfaces stay visually identical — see adversary-dossier).   */
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
/* Command catalog + class labels                                      */
/* ------------------------------------------------------------------ */

const COMMAND_CATALOG: readonly ScenarioCommandTemplateV1[] = [
  'observe',
  'increase_monitoring',
  'isolate',
  'restrict_access',
  'revoke_credentials',
  'restart_service',
  'rollback_deployment',
];

const COMMAND_CLASS: Record<ScenarioCommandTemplateV1, string> = {
  observe: 'Class 0',
  increase_monitoring: 'Class 1',
  isolate: 'Class 2',
  restrict_access: 'Class 2',
  revoke_credentials: 'Class 2',
  restart_service: 'Class 3',
  rollback_deployment: 'Class 3',
};

function humanizeCommand(command: string): string {
  return command
    .split('_')
    .map((word, index) => (index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(' ');
}

const KIND_LABEL: Record<GhostDecisionPointV1['kind'], string> = {
  executed_action: 'Executed action',
  inaction_window: 'Inaction window',
};

interface ModeOption {
  value: GhostBranchModeV1;
  title: string;
  hint: string;
}

const MODE_OPTIONS: readonly ModeOption[] = [
  { value: 'substitute', title: 'Do something else', hint: 'Run a different command here' },
  { value: 'do_nothing', title: 'Do nothing', hint: 'Take no action at all' },
  { value: 'shift', title: 'Act earlier or later', hint: 'Move the same command in time' },
];

// Shift magnitudes offered as buttons (seconds); ±3600 is the server-enforced ceiling.
const SHIFT_STEPS = [120, 300, 600] as const;

function decisionClassLabel(decision: GhostDecisionPointV1): string | null {
  if (decision.actionClass) {
    return decision.actionClass;
  }
  if (decision.scenarioCommand) {
    return COMMAND_CLASS[decision.scenarioCommand];
  }
  return null;
}

function formatShift(seconds: number): string {
  const sign = seconds < 0 ? '−' : '+';
  const minutes = Math.abs(seconds) / 60;
  return `${sign}${String(minutes)}m`;
}

/* ------------------------------------------------------------------ */
/* Outcome comparison (tone only — never a fabricated ghost score)     */
/* ------------------------------------------------------------------ */

type OutcomeTone = 'accent' | 'warning' | 'neutral';

function verdictTone(real: GhostOutcomeV1, ghost: GhostOutcomeV1): OutcomeTone {
  const realBad = real.compromisedCount + (real.breachOccurred ? 1 : 0);
  const ghostBad = ghost.compromisedCount + (ghost.breachOccurred ? 1 : 0);
  if (ghostBad < realBad) {
    return 'accent';
  }
  if (ghostBad > realBad) {
    return 'warning';
  }
  return 'neutral';
}

const VERDICT_TONE: Record<OutcomeTone, string> = {
  accent: 'border-[var(--aegis-status-normal)]/40 bg-[var(--aegis-status-normal-bg)]',
  warning: 'border-[var(--aegis-status-suspicious)]/40 bg-[var(--aegis-status-suspicious-bg)]',
  neutral: 'border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)]',
};

const CARD_TONE: Record<OutcomeTone, string> = {
  accent: 'border-[var(--aegis-status-normal)]/30 bg-[var(--aegis-status-normal-bg)]/40',
  warning: 'border-[var(--aegis-status-suspicious)]/30 bg-[var(--aegis-status-suspicious-bg)]/40',
  neutral: 'border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)]',
};

/* ------------------------------------------------------------------ */
/* Sealed (mid-run) state                                              */
/* ------------------------------------------------------------------ */

function SealedState({ runStatus }: { runStatus: string | undefined }) {
  return (
    <Surface className="p-6" data-testid="ghost-branch-sealed" aria-label="Ghost branch sealed">
      <div className="flex flex-col items-center gap-3 text-center">
        <span
          aria-hidden="true"
          className="flex size-11 items-center justify-center rounded-full border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] text-lg"
        >
          🔒
        </span>
        <h2 className="font-[family-name:var(--aegis-font-display)] text-lg font-semibold text-[var(--aegis-text-primary)]">
          Ghost branch opens after the run ends
        </h2>
        <p className="max-w-md text-sm leading-6 text-[var(--aegis-text-secondary)]">
          Counterfactual replay only makes sense once the real timeline is settled. When this run
          reaches a terminal state you can fork any decision and compare the true alternate outcome.
        </p>
        {runStatus ? <Pill>{`Run status: ${runStatus}`}</Pill> : null}
      </div>
    </Surface>
  );
}

/* ------------------------------------------------------------------ */
/* Decision picker                                                     */
/* ------------------------------------------------------------------ */

function DecisionButton({
  decision,
  selected,
  onSelect,
}: {
  decision: GhostDecisionPointV1;
  selected: boolean;
  onSelect: () => void;
}) {
  const classLabel = decisionClassLabel(decision);
  return (
    <button
      type="button"
      data-testid={`ghost-decision-${decision.decisionRef}`}
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        'group w-full px-3 py-3 text-left transition-colors',
        'focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-inset focus-visible:ring-[var(--aegis-focus-ring)]',
        selected
          ? 'bg-[var(--aegis-surface-raised)] shadow-[inset_2px_0_0_var(--aegis-accent-line)]'
          : 'hover:bg-[var(--aegis-surface-hover)]',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span
          className="min-w-0 truncate text-sm font-medium text-[var(--aegis-text-primary)]"
          title={decision.label}
        >
          {decision.label}
        </span>
        <span className="flex-none font-mono text-[0.7rem] text-[var(--aegis-text-muted)] tabular-nums">
          seq {decision.sequence}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Pill tone={decision.kind === 'inaction_window' ? 'warning' : 'accent'}>
          {KIND_LABEL[decision.kind]}
        </Pill>
        {classLabel ? <Pill>{classLabel}</Pill> : null}
        {decision.scenarioCommand ? <Pill>{humanizeCommand(decision.scenarioCommand)}</Pill> : null}
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Outcome card (real / ghost)                                         */
/* ------------------------------------------------------------------ */

function OutcomeCard({
  title,
  outcome,
  score,
  tone,
  testid,
}: {
  title: string;
  outcome: GhostOutcomeV1;
  score: number | null;
  tone: OutcomeTone;
  testid: string;
}) {
  return (
    <div
      data-testid={testid}
      className={cn(
        'flex flex-col gap-3 rounded-[var(--aegis-radius-lg)] border p-4',
        CARD_TONE[tone],
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-secondary)]')}>
          {title}
        </span>
        <span className="text-xs text-[var(--aegis-text-muted)]">{outcome.label}</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <MetricTile label="Compromised" value={outcome.compromisedCount} />
        <MetricTile label="Contained" value={outcome.containedCount} />
        <MetricTile label="Breach" value={outcome.breachOccurred ? 'Yes' : 'No'} />
      </div>
      {score !== null ? (
        <MetricTile label="Overall score" value={score} data-testid={`${testid}-score`} />
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Results                                                             */
/* ------------------------------------------------------------------ */

function GhostResults({ result }: { result: GhostBranchResultV1 }) {
  const tone = verdictTone(result.realOutcome, result.ghostOutcome);
  return (
    <Surface className="p-5 lg:p-6" aria-label="Ghost branch outcome" data-testid="ghost-results">
      <div className="flex flex-col gap-6">
        <div
          className={cn('rounded-[var(--aegis-radius-md)] border px-4 py-3', VERDICT_TONE[tone])}
          data-testid="ghost-verdict"
        >
          <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
            Counterfactual verdict
          </span>
          <p className="mt-1 text-base font-semibold leading-6 text-[var(--aegis-text-primary)]">
            {result.verdict}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Pill>{`diverged at seq ${String(result.divergenceSequence)}`}</Pill>
            <Pill>{`${String(result.stepsSimulated)} steps simulated`}</Pill>
            <MonoChip value={result.resultHash} label="result hash" variant="checksum" />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <OutcomeCard
            title="Real timeline"
            outcome={result.realOutcome}
            score={result.realOverallScore ?? null}
            tone="neutral"
            testid="ghost-real"
          />
          <OutcomeCard
            title="Ghost timeline"
            outcome={result.ghostOutcome}
            score={null}
            tone={tone}
            testid="ghost-ghost"
          />
        </div>

        <div className="flex flex-col gap-3">
          <ZoneHeading count={result.assetDiffs.length}>Asset outcome diffs</ZoneHeading>
          {result.assetDiffs.length === 0 ? (
            <p className="text-sm text-[var(--aegis-text-muted)]">
              No asset ended in a different state.
            </p>
          ) : (
            <ul
              className="divide-y divide-[var(--aegis-border-subtle)]"
              data-testid="ghost-asset-diffs"
            >
              {result.assetDiffs.map((diff) => (
                <li
                  key={diff.assetId}
                  data-testid={`ghost-diff-${diff.assetId}`}
                  className="flex flex-wrap items-center gap-2 py-2 text-sm"
                >
                  <MonoChip value={diff.assetId} label="asset id" />
                  <span className="font-mono text-xs text-[var(--aegis-text-muted)]">
                    {diff.realStatus}
                  </span>
                  <span className="sr-only">changed to</span>
                  <span aria-hidden="true" className="text-[var(--aegis-text-muted)]">
                    →
                  </span>
                  <span className="font-mono text-xs font-semibold text-[var(--aegis-text-primary)]">
                    {diff.ghostStatus}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <ZoneHeading count={result.ghostTimeline.length}>Divergence timeline</ZoneHeading>
          <GhostTimeline beats={result.ghostTimeline} startSimTime={result.divergenceSimTime} />
        </div>
      </div>
    </Surface>
  );
}

/* ------------------------------------------------------------------ */
/* Workbench (terminal only)                                           */
/* ------------------------------------------------------------------ */

function GhostBranchWorkbench({ runId }: { runId: string }) {
  const decisionQuery = useGhostDecisionPoints(runId, true);
  const mutation = useGhostRunMutation(runId);

  const decisionPoints = useMemo(
    () => decisionQuery.data?.decisionPoints ?? [],
    [decisionQuery.data],
  );

  // Selection + form state. Target/command carry an override so switching decisions re-derives
  // sensible defaults (target ← the decision's asset) without a sync effect.
  const [decisionRef, setDecisionRef] = useState('');
  const [mode, setMode] = useState<GhostBranchModeV1>('substitute');
  const [commandOverride, setCommandOverride] = useState<ScenarioCommandTemplateV1 | ''>('');
  const [targetOverride, setTargetOverride] = useState<string | null>(null);
  const [shiftSimSeconds, setShiftSimSeconds] = useState(0);

  // Effective selection auto-falls-back to the first decision until the operator picks one.
  const activeRef = decisionRef || decisionPoints[0]?.decisionRef || '';
  const selectedDecision = decisionPoints.find((d) => d.decisionRef === activeRef);

  const alternateCommand = commandOverride;
  const alternateTarget = targetOverride ?? selectedDecision?.targetAssetId ?? '';
  const shiftSupported = Boolean(selectedDecision?.scenarioCommand);
  const needsTarget = !selectedDecision?.targetAssetId;

  const handleSelectDecision = (ref: string) => {
    setDecisionRef(ref);
    setMode('substitute');
    setCommandOverride('');
    setTargetOverride(null);
    setShiftSimSeconds(0);
  };

  const request = useMemo<GhostBranchRequestV1 | null>(() => {
    if (!selectedDecision) {
      return null;
    }
    const ref = selectedDecision.decisionRef;
    if (mode === 'substitute') {
      if (!alternateCommand) {
        return null;
      }
      const target = alternateTarget.trim();
      if (!target) {
        return null;
      }
      return {
        schemaVersion: 1,
        decisionRef: ref,
        mode: 'substitute',
        alternateCommand,
        alternateTargetAssetId: target,
      };
    }
    if (mode === 'do_nothing') {
      return { schemaVersion: 1, decisionRef: ref, mode: 'do_nothing' };
    }
    // shift
    if (!shiftSupported || shiftSimSeconds === 0 || Math.abs(shiftSimSeconds) > 3600) {
      return null;
    }
    return { schemaVersion: 1, decisionRef: ref, mode: 'shift', shiftSimSeconds };
  }, [selectedDecision, mode, alternateCommand, alternateTarget, shiftSupported, shiftSimSeconds]);

  const canRun = request !== null && !mutation.isPending;
  const error = mutation.error;
  const isRunNotTerminal = error?.code === 'RUN_NOT_TERMINAL';

  const handleRun = () => {
    if (request) {
      mutation.mutate(request);
    }
  };

  return (
    <section
      aria-label="Ghost branch"
      data-testid="ghost-branch-panel"
      className="flex flex-col gap-6"
    >
      <Surface className="p-6 lg:p-7">
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-accent-cyan)]')}>
              Ghost branch
            </span>
            <h2 className="font-[family-name:var(--aegis-font-display)] text-2xl font-semibold tracking-[0.01em] text-[var(--aegis-text-primary)]">
              What if you had decided differently?
            </h2>
            <p className="max-w-xl text-sm leading-6 text-[var(--aegis-text-secondary)]">
              Fork one of your real decision points. The deterministic engine re-simulates from that
              moment and returns the true alternate timeline — not a guess.
            </p>
          </div>

          {decisionQuery.isLoading ? (
            <LoadingState message="Loading forkable decision points" />
          ) : decisionQuery.isError ? (
            <EmptyState
              title="Decision points unavailable"
              description={
                decisionQuery.error instanceof ApiClientError
                  ? `${decisionQuery.error.code}: ${decisionQuery.error.message}`
                  : 'Failed to load forkable decision points'
              }
              data-testid="ghost-decisions-error"
            />
          ) : decisionPoints.length === 0 ? (
            <EmptyState
              title="No forkable decisions"
              description="This run has no executed actions or inaction windows to branch from."
              data-testid="ghost-decisions-empty"
            />
          ) : (
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8">
              {/* Decision picker */}
              <div className="flex min-w-0 flex-col gap-3">
                <ZoneHeading count={decisionPoints.length}>Decision point</ZoneHeading>
                <div
                  className="divide-y divide-[var(--aegis-border-subtle)] overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)]"
                  data-testid="ghost-decision-list"
                >
                  {decisionPoints.map((decision) => (
                    <DecisionButton
                      key={decision.decisionRef}
                      decision={decision}
                      selected={decision.decisionRef === activeRef}
                      onSelect={() => {
                        handleSelectDecision(decision.decisionRef);
                      }}
                    />
                  ))}
                </div>
              </div>

              {/* Alternate config */}
              <div className="flex min-w-0 flex-col gap-4 border-t border-[var(--aegis-border-subtle)] pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
                <ZoneHeading>Alternate</ZoneHeading>

                <fieldset className="flex flex-col gap-2">
                  <legend
                    className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}
                  >
                    What if you had…
                  </legend>
                  <div className="flex flex-col gap-1.5">
                    {MODE_OPTIONS.map((option) => {
                      const disabled = option.value === 'shift' && !shiftSupported;
                      const id = `ghost-mode-${option.value}`;
                      return (
                        <label
                          key={option.value}
                          htmlFor={id}
                          className={cn(
                            'flex cursor-pointer items-start gap-2.5 rounded-[var(--aegis-radius-md)] border px-3 py-2 transition-colors',
                            mode === option.value
                              ? 'border-[var(--aegis-accent-line)]/50 bg-[var(--aegis-accent-soft)]'
                              : 'border-[var(--aegis-border-subtle)] hover:bg-[var(--aegis-surface-hover)]',
                            disabled && 'cursor-not-allowed opacity-50',
                          )}
                        >
                          <input
                            id={id}
                            type="radio"
                            name="ghost-mode"
                            value={option.value}
                            checked={mode === option.value}
                            disabled={disabled}
                            onChange={() => {
                              setMode(option.value);
                            }}
                            className="mt-0.5 accent-[var(--aegis-accent-cyan)]"
                          />
                          <span className="flex flex-col">
                            <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
                              {option.title}
                            </span>
                            <span className="text-xs text-[var(--aegis-text-muted)]">
                              {disabled ? 'Needs an executed action to move' : option.hint}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>

                {mode === 'substitute' ? (
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-1.5">
                      <label
                        htmlFor="ghost-alt-command"
                        className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}
                      >
                        Alternate command
                      </label>
                      <select
                        id="ghost-alt-command"
                        value={alternateCommand}
                        onChange={(event) => {
                          setCommandOverride(event.target.value as ScenarioCommandTemplateV1 | '');
                        }}
                        className="w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2 text-sm text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)]"
                      >
                        <option value="">Choose a command…</option>
                        {COMMAND_CATALOG.map((command) => (
                          <option key={command} value={command}>
                            {humanizeCommand(command)} · {COMMAND_CLASS[command]}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label
                        htmlFor="ghost-alt-target"
                        className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}
                      >
                        Target asset{needsTarget ? ' (required)' : ''}
                      </label>
                      <input
                        id="ghost-alt-target"
                        type="text"
                        value={alternateTarget}
                        onChange={(event) => {
                          setTargetOverride(event.target.value);
                        }}
                        placeholder="asset:…"
                        className="w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2 font-mono text-sm text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)]"
                      />
                      <span className="text-xs text-[var(--aegis-text-muted)]">
                        {needsTarget
                          ? 'This inaction window has no target — name the asset to act on.'
                          : 'Defaults to the asset you originally acted on.'}
                      </span>
                    </div>
                  </div>
                ) : null}

                {mode === 'shift' ? (
                  <div className="flex flex-col gap-2">
                    <span
                      id="ghost-shift-label"
                      className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}
                    >
                      Shift timing
                    </span>
                    <div
                      role="group"
                      aria-labelledby="ghost-shift-label"
                      className="flex flex-wrap items-center gap-1.5"
                    >
                      {SHIFT_STEPS.map((step) => {
                        const seconds = -step;
                        const active = shiftSimSeconds === seconds;
                        return (
                          <ShiftButton
                            key={`earlier-${String(step)}`}
                            seconds={seconds}
                            active={active}
                            onToggle={() => {
                              setShiftSimSeconds(active ? 0 : seconds);
                            }}
                          />
                        );
                      })}
                      <span
                        aria-hidden="true"
                        className="mx-0.5 h-4 w-px bg-[var(--aegis-border-subtle)]"
                      />
                      {SHIFT_STEPS.map((step) => {
                        const active = shiftSimSeconds === step;
                        return (
                          <ShiftButton
                            key={`later-${String(step)}`}
                            seconds={step}
                            active={active}
                            onToggle={() => {
                              setShiftSimSeconds(active ? 0 : step);
                            }}
                          />
                        );
                      })}
                    </div>
                    <span className="text-xs text-[var(--aegis-text-muted)]">
                      {shiftSimSeconds === 0
                        ? 'Pick an earlier (−) or later (+) offset.'
                        : `Selected offset: ${formatShift(shiftSimSeconds)}`}
                    </span>
                  </div>
                ) : null}

                <div className="flex flex-col gap-2 pt-1">
                  <button
                    type="button"
                    data-testid="ghost-run"
                    onClick={handleRun}
                    disabled={!canRun}
                    className={cn(
                      'inline-flex items-center justify-center gap-2 rounded-[var(--aegis-radius-md)] border px-4 py-2 text-sm font-semibold transition-colors',
                      'focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)]',
                      canRun
                        ? 'border-[var(--aegis-accent-line)]/60 bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-cyan)] motion-safe:hover:brightness-110'
                        : 'cursor-not-allowed border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] text-[var(--aegis-text-muted)]',
                    )}
                  >
                    {mutation.isPending ? 'Re-simulating…' : 'Run ghost branch'}
                  </button>
                  <div aria-live="polite" className="min-h-5 text-xs">
                    {mutation.isPending ? (
                      <span className="text-[var(--aegis-accent-cyan)]">
                        Re-simulating alternate timeline…
                      </span>
                    ) : null}
                    {error ? (
                      <span
                        data-testid="ghost-error"
                        className="text-[var(--aegis-status-compromised)]"
                      >
                        {isRunNotTerminal
                          ? 'This run is not in a terminal state — ghost branch is available only after it ends.'
                          : `${error.code}: ${error.message}`}
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </Surface>

      {mutation.data ? <GhostResults result={mutation.data} /> : null}
    </section>
  );
}

function ShiftButton({
  seconds,
  active,
  onToggle,
}: {
  seconds: number;
  active: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      data-testid={`ghost-shift-${String(seconds)}`}
      onClick={onToggle}
      className={cn(
        'rounded-full border px-2.5 py-1 text-xs font-medium tabular-nums transition-colors',
        'focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)]',
        active
          ? 'border-[var(--aegis-accent-line)]/60 bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-cyan)]'
          : 'border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] text-[var(--aegis-text-secondary)] hover:bg-[var(--aegis-surface-hover)]',
      )}
    >
      {formatShift(seconds)}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Entry point                                                         */
/* ------------------------------------------------------------------ */

export function GhostBranchPanel({ runId }: { runId: string }) {
  const runQuery = useRun(runId);
  const terminal = isTerminalRunStatus(runQuery.data?.status);

  // Fog-of-war gate: mid-run the workbench never mounts, so the ghost endpoints are untouched.
  if (!terminal) {
    return <SealedState runStatus={runQuery.data?.status} />;
  }
  return <GhostBranchWorkbench runId={runId} />;
}
