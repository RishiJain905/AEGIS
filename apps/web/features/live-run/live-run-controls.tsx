'use client';

import type { ReactNode } from 'react';

import { Button } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run/live-run-provider';
import { useRunCommands } from '@/features/live-run/use-run-commands';

/**
 * A labelled cluster of transport controls. The label is the same word the status rail
 * uses for the fact these buttons change — SIM buttons move simulated time, LINK buttons
 * manage delivery to this screen — so state and control read as one system.
 */
function ControlGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      role="group"
      aria-label={`${label} controls`}
      className="flex items-stretch overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_72%,transparent)] shadow-[var(--aegis-shadow-control)] backdrop-blur-xl"
    >
      <span className="flex select-none items-center border-r border-[var(--aegis-border-subtle)] px-2 font-[family-name:var(--aegis-font-display)] text-[0.5625rem] font-semibold uppercase tracking-[0.18em] text-[var(--aegis-text-faint)]">
        {label}
      </span>
      <div className="flex items-center gap-0.5 p-1">{children}</div>
    </div>
  );
}

export function LiveRunControls() {
  const liveRun = useLiveRun();
  if (liveRun === null || !liveRun.isLiveMode) {
    return null;
  }

  const { pause, resume, stop, step } = useRunCommands(liveRun.runId);
  const locallyPaused = liveRun.state.locallyPaused;
  const runStatus = liveRun.state.runStatus;
  const isPaused = runStatus === 'paused';
  // The simulator only accepts a lifecycle command in the state that command is defined
  // for: STEP advances a RUNNING run, and the API answers 409 for anything else. Deriving
  // the button's enabled state from the same rule is what keeps the two honest — offering
  // Step on a paused run just moved the rejection from the control to a toast.
  const isTerminal = runStatus === 'stopped' || runStatus === 'completed';
  const stepDisabledReason = isTerminal
    ? 'This run has ended — its timeline is read-only.'
    : isPaused
      ? 'Stepping advances the live simulation. Resume the sim first.'
      : undefined;

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="live-run-controls">
      <ControlGroup label="Sim">
        <Button
          size="sm"
          variant="ghost"
          className="text-xs"
          data-testid="live-step"
          disabled={step.isPending || stepDisabledReason !== undefined}
          title={stepDisabledReason}
          onClick={() => {
            step.mutate();
          }}
        >
          Step
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-xs"
          data-testid="live-pause-resume"
          disabled={pause.isPending || resume.isPending || isTerminal}
          title={isTerminal ? 'This run has ended — its timeline is read-only.' : undefined}
          onClick={() => {
            if (isPaused) {
              resume.mutate();
            } else {
              pause.mutate();
            }
          }}
        >
          {/* Copy stays "Pause sim"/"Resume sim" — the guided walkthrough teaches these
              buttons by name against their client-side "updates" counterparts. */}
          {isPaused ? 'Resume sim' : 'Pause sim'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-xs text-[var(--aegis-risk-high)] hover:text-[var(--aegis-risk-high)]"
          data-testid="live-stop"
          disabled={stop.isPending || isTerminal}
          title={isTerminal ? 'This run has already ended.' : 'End the run for good.'}
          onClick={() => {
            stop.mutate();
          }}
        >
          Stop
        </Button>
      </ControlGroup>

      <ControlGroup label="Link">
        <Button
          size="sm"
          variant="ghost"
          className="text-xs"
          data-testid="live-local-pause"
          aria-pressed={locallyPaused}
          title={
            locallyPaused
              ? 'Apply the live events queued while the view was held.'
              : 'Freeze this screen; the simulation keeps running underneath.'
          }
          onClick={() => {
            liveRun.setLocallyPaused(!locallyPaused);
          }}
        >
          {locallyPaused ? 'Resume updates' : 'Pause updates'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-xs"
          data-testid="live-resync"
          title="Reload the authoritative snapshot and replay anything missed."
          onClick={() => void liveRun.resync()}
        >
          Resync
        </Button>
      </ControlGroup>
    </div>
  );
}
