'use client';

import { useRef, type KeyboardEvent } from 'react';

import { LiveRunControls, useLiveRun } from '@/features/live-run';
import { ActionResultSlot, AssetCommandBar } from '@/features/operator-actions';
import { RunTape } from '@/features/timeline';
import { isCockpitShortcutKey } from '@/lib/cockpit-keys';
import { isTypingTarget } from '@/lib/keyboard';
import { isRunTerminal } from '@/lib/run-status';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

import { CopilotChip } from './copilot-chip';
import { useToolbarRovingFocus } from './use-toolbar-roving-focus';

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

/** Hairline between console clusters; decoration only, hidden when the band wraps tight. */
function ClusterRule() {
  return (
    <span
      aria-hidden="true"
      className="hidden h-8 w-px shrink-0 bg-[var(--aegis-border-subtle)] lg:block"
    />
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
  const chronicleOpen = useCockpitUiStore((state) => state.chronicleOpen);
  const setChronicleOpen = useCockpitUiStore((state) => state.setChronicleOpen);

  // One Tab stop for the whole band; arrows move between its controls.
  const bandRef = useRef<HTMLDivElement>(null);
  useToolbarRovingFocus(bandRef);

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
    // A bound shortcut always wins over composing. The console is the cockpit's single Tab
    // stop, so seeding every letter here made `A`/`I`/`C`/`T` unreachable from the one place
    // a keyboard operator stands; letting them bubble is what makes them reachable at all.
    if (isCockpitShortcutKey(event.key)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    seedCopilotComposer(event.key);
  };

  return (
    <div className="flex shrink-0 flex-col gap-2" data-testid="cockpit-console">
      <TimelineSemanticsNotice />
      <ActionResultSlot />
      <div
        ref={bandRef}
        role="toolbar"
        aria-label="Console"
        aria-orientation="horizontal"
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
          <RunTape
            chrome="console"
            chronicle={{ open: chronicleOpen, setOpen: setChronicleOpen }}
          />
        </div>
        <CopilotChip runId={runId} />
      </div>
    </div>
  );
}
