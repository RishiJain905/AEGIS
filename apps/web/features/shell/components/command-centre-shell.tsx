'use client';

import { cn } from '@aegis/ui';
import { useEffect } from 'react';

import { ConnectionHealthBanner, LiveRunProvider } from '@/features/live-run';
import { CommandPalette } from '@/features/shell/components/command-palette';
import { OperationsRail } from '@/features/shell/components/operations-rail';
import { RunWorkspace } from '@/features/shell/components/run-workspace';
import { StatusStrip } from '@/features/shell/components/status-strip';
import { useKeyboardShortcuts } from '@/features/shell/hooks/use-keyboard-shortcuts';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface CommandCentreShellProps {
  runId?: string;
  incidentId?: string;
  /**
   * The run a run-scoped page (after-action, reports) is ABOUT, when it does not want the
   * full live cockpit. Feeds only the status rail, so the header reports the viewed run's
   * real state instead of placeholder facts — without mounting LiveRunProvider.
   */
  statusRunId?: string;
  children?: React.ReactNode;
}

function CommandCentreShellInner({
  runId,
  incidentId,
  statusRunId,
  children,
}: CommandCentreShellProps) {
  const resetForRun = useWorkspaceUiStore((state) => state.resetForRun);
  // A run without page content of its own gets the viewport-height graph workspace; every
  // other shell route (scenarios, reports, admin, after-action) keeps normal page flow.
  const isRunWorkspace = Boolean(runId) && !children;

  useEffect(() => {
    resetForRun(runId ?? null);
  }, [runId, resetForRun]);

  return (
    <>
      <CommandPalette />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <OperationsRail />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <StatusStrip runId={runId ?? statusRunId} />
          {/* Zero-height slot: the banner overlays the content instead of displacing it, so a
              connection-health flip never resizes the graph canvas or the docks. */}
          <ConnectionHealthBanner />
          <main
            id="command-centre-content"
            className={
              isRunWorkspace
                ? 'flex min-h-0 flex-1 flex-col p-3 xl:p-4'
                : 'flex min-h-0 flex-1 flex-col gap-5 p-5 xl:p-6'
            }
          >
            {isRunWorkspace && runId ? (
              <RunWorkspace runId={runId} incidentId={incidentId} />
            ) : (
              children
            )}
          </main>
        </div>
      </div>
    </>
  );
}

export function CommandCentreShell({
  runId,
  incidentId,
  statusRunId,
  children,
}: CommandCentreShellProps) {
  useKeyboardShortcuts();
  const isRunWorkspace = Boolean(runId) && !children;

  return (
    <div
      className={cn(
        'aegis-command-shell flex min-h-screen flex-col',
        // The run workspace is a fixed-height cockpit on desktop so the graph can claim the
        // viewport; below xl there is not enough width for three columns, so the page falls
        // back to normal scrolling flow.
        isRunWorkspace && 'xl:h-[100dvh] xl:min-h-0 xl:overflow-hidden',
      )}
      data-testid="command-centre-shell"
    >
      <a className="skip-link" href="#command-centre-content">
        Skip to command workspace
      </a>
      {runId ? (
        <LiveRunProvider runId={runId}>
          <CommandCentreShellInner runId={runId} incidentId={incidentId}>
            {children}
          </CommandCentreShellInner>
        </LiveRunProvider>
      ) : (
        <CommandCentreShellInner runId={runId} incidentId={incidentId} statusRunId={statusRunId}>
          {children}
        </CommandCentreShellInner>
      )}
    </div>
  );
}
