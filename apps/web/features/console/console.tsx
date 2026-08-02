'use client';

import type { KeyboardEvent } from 'react';

import { Button } from '@aegis/ui';

import { LiveRunControls, useLiveRun } from '@/features/live-run';
import { AssetCommandBar } from '@/features/operator-actions';
import { RunTape } from '@/features/timeline';
import { isTypingTarget } from '@/lib/keyboard';
import { isRunTerminal } from '@/lib/run-status';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import { CopilotChip } from './copilot-chip';

/**
 * The execution-semantics ribbon above the console (BUG-012). Operator actions do not
 * queue behind a paused simulator — they execute against the frozen timeline — and once a
 * run ends they cannot execute at all. Both facts are said exactly where commands are
 * issued, in the same vocabulary as the SIM instrument in the status rail.
 */
function TimelineSemanticsNotice() {
  const liveRun = useLiveRun();
  if (liveRun === null || !liveRun.isLiveMode) {
    return null;
  }
  const runStatus = liveRun.state.runStatus;

  if (runStatus === 'paused') {
    return (
      <p
        role="status"
        data-testid="frozen-timeline-notice"
        className="flex flex-wrap items-baseline gap-x-2 rounded-[var(--aegis-radius-md)] border border-[color-mix(in_srgb,var(--aegis-status-suspicious)_40%,transparent)] bg-[color-mix(in_srgb,var(--aegis-status-suspicious)_8%,var(--aegis-surface-panel))] px-3 py-1.5 text-xs leading-5 text-[var(--aegis-text-secondary)]"
      >
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.14em] text-[var(--aegis-status-suspicious)]">
          Sim paused
        </span>
        Commands still execute — against the frozen timeline, effective immediately.
      </p>
    );
  }

  if (isRunTerminal(runStatus)) {
    return (
      <p
        role="status"
        data-testid="run-ended-notice"
        className="flex flex-wrap items-baseline gap-x-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_70%,transparent)] px-3 py-1.5 text-xs leading-5 text-[var(--aegis-text-muted)]"
      >
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]">
          Run ended
        </span>
        The timeline is read-only; commands can no longer execute.
      </p>
    );
  }

  return null;
}

/**
 * Collapse the rail and both docks together, or restore them all.
 *
 * Transitional: it lives here only while the docks still exist. Once the docks are gone
 * (cockpit rework phase 5) there is nothing left to hide and this control dies with them.
 */
function FocusStageButton() {
  const regions = useWorkspaceUiStore((state) => state.panelPreferences.regions);
  const setPanelCollapsed = useWorkspaceUiStore((state) => state.setPanelCollapsed);

  const focused =
    (regions.operationsRail?.collapsed ?? false) &&
    (regions.leftDock?.collapsed ?? false) &&
    (regions.rightDock?.collapsed ?? false);

  return (
    <Button
      variant={focused ? 'default' : 'outline'}
      size="sm"
      className="text-xs"
      data-testid="focus-stage"
      aria-pressed={focused}
      onClick={() => {
        setPanelCollapsed('operationsRail', !focused);
        setPanelCollapsed('leftDock', !focused);
        setPanelCollapsed('rightDock', !focused);
      }}
    >
      {focused ? 'Restore panels' : 'Focus graph'}
    </Button>
  );
}

/** Hairline between console clusters; decoration only, hidden when the band wraps tight. */
function ClusterRule() {
  return (
    <span aria-hidden="true" className="hidden h-8 w-px shrink-0 bg-[var(--aegis-border-subtle)] lg:block" />
  );
}

export interface ConsoleProps {
  runId: string;
}

/**
 * The Console — one fused command band across the foot of the stage. Everything that
 * *commits* lives here, left to right: the SIM/LINK transport clusters, the selected-asset
 * command cluster, the run tape, and the copilot presence chip. The clusters keep their
 * own components, testids and semantics; the console only gives them a shared band so
 * control reads as one surface instead of three stacked rows.
 *
 * The band is also a command line to the agents: typing a printable character with the
 * console focused opens the copilot sheet and routes the keystroke into its composer.
 *
 * The frozen-timeline / run-ended ribbon renders as a thin notice line directly above the
 * band, in the same place commands are issued.
 */
export function Console({ runId }: ConsoleProps) {
  const seedCopilotComposer = useCockpitUiStore((state) => state.seedCopilotComposer);

  // Printable keystrokes on console furniture route to the copilot. Space and Enter stay
  // with whatever button is focused; modified chords and typing contexts pass through.
  const handleBandKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (event.key.length !== 1 || event.key === ' ') {
      return;
    }
    if (isTypingTarget(event.target)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    seedCopilotComposer(event.key);
  };

  return (
    <div className="flex shrink-0 flex-col gap-2" data-testid="cockpit-console">
      <TimelineSemanticsNotice />
      <div
        role="group"
        aria-label="Console"
        onKeyDown={handleBandKeyDown}
        className="flex min-h-[4.5rem] w-full flex-wrap items-center gap-x-3 gap-y-2 rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_82%,transparent)] px-3 py-2 shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl"
      >
        <LiveRunControls />
        <ClusterRule />
        <div className="min-w-[18rem] flex-[1.2] basis-[24rem]">
          <AssetCommandBar runId={runId} chrome="console" />
        </div>
        <ClusterRule />
        <div className="min-w-[16rem] flex-1 basis-[20rem]">
          <RunTape chrome="console" />
        </div>
        <CopilotChip runId={runId} />
        <FocusStageButton />
      </div>
    </div>
  );
}
