'use client';

import {
  CinematicAccessibilityFallback,
  CinematicModeToggle,
  CinematicTransportControls,
  useCinematicDirectorController,
} from '@/features/cinematic-replay';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';
import { HistoricalModeBanner } from '@/features/replay/components/historical-mode-banner';
import { ReplayBookmarks } from '@/features/replay/components/replay-bookmarks';
import { ReplayComparisonPanel } from '@/features/replay/components/replay-comparison-panel';
import { ReplayInspectorPanel } from '@/features/replay/components/replay-inspector-panel';
import { ReplayTransportControls } from '@/features/replay/components/replay-transport-controls';
import { ReplayVisualization } from '@/features/replay/components/replay-visualization';
import { useReplayKeyboard } from '@/features/replay/hooks/use-replay-keyboard';
import { ReplayProvider } from '@/features/replay/replay-provider';
import { CommandPalette } from '@/features/shell/components/command-palette';
import { OperationsRail } from '@/features/shell/components/operations-rail';
import { StatusStrip } from '@/features/shell/components/status-strip';
import { useKeyboardShortcuts } from '@/features/shell/hooks/use-keyboard-shortcuts';
import { ReplayTimelineView } from '@/features/timeline/replay/replay-timeline-view';
import { useReplayStore } from '@/stores/replay-store';

export interface ReplayCommandCentreShellProps {
  runId: string;
}

function ReplayStatusExtras() {
  const cursor = useReplayStore((state) => state.cursor);
  const provenance = useReplayStore((state) => state.provenance);
  const mode = useReplayStore((state) => state.mode);
  const cinematicMode = useCinematicReplayStore((state) => state.mode);
  const cinematicBeat = useCinematicReplayStore((state) => state.lastApplied);

  return (
    <div
      className="flex flex-wrap items-center gap-3 border-b border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] px-4 py-2 text-xs"
      data-testid="replay-status-extras"
      role="status"
      aria-live="polite"
    >
      <span data-testid="replay-mode-label">Mode: {mode}</span>
      <span data-testid="cinematic-session-mode-label">
        Presentation: {cinematicMode === 'cinematic' ? 'cinematic' : 'normal'}
      </span>
      {cursor ? <span data-testid="replay-sequence-label">Sequence: {cursor.sequence}</span> : null}
      {cinematicMode === 'cinematic' && cinematicBeat ? (
        <span data-testid="cinematic-sync-label">
          Cinematic beat @ seq {cinematicBeat.sequence}
        </span>
      ) : null}
      {provenance ? (
        <span data-testid="replay-applied-range">
          Applied: {provenance.appliedFromSequence}–{provenance.appliedToSequence} (
          {provenance.mode})
        </span>
      ) : null}
    </div>
  );
}

function ReplayShellInner({ runId }: ReplayCommandCentreShellProps) {
  useKeyboardShortcuts();
  useReplayKeyboard();
  useCinematicDirectorController(runId);

  return (
    <>
      <CommandPalette />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <OperationsRail />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <StatusStrip runId={runId} />
          <ReplayStatusExtras />
          <HistoricalModeBanner />
          <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 xl:flex-row">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CinematicModeToggle />
              </div>
              <ReplayTransportControls />
              <CinematicTransportControls />
              <ReplayVisualization />
              <CinematicAccessibilityFallback />
              <div className="grid gap-4 lg:grid-cols-2">
                <ReplayBookmarks />
                <ReplayComparisonPanel />
              </div>
              <ReplayTimelineView />
            </div>
            <ReplayInspectorPanel />
          </div>
        </div>
      </div>
    </>
  );
}

export function ReplayCommandCentreShell({ runId }: ReplayCommandCentreShellProps) {
  return (
    <div
      className="flex min-h-screen flex-col bg-[var(--aegis-surface-base)]"
      data-testid="command-centre-shell"
      data-aegis-mode="historical"
    >
      <ReplayProvider runId={runId}>
        <ReplayShellInner runId={runId} />
      </ReplayProvider>
    </div>
  );
}
