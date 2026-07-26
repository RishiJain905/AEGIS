'use client';

import { DisconnectedState, cn } from '@aegis/ui';
import { useEffect } from 'react';

import { ConnectionHealthBanner, LiveRunProvider, useLiveRun } from '@/features/live-run';
import { CommandPalette } from '@/features/shell/components/command-palette';
import { OperationsRail } from '@/features/shell/components/operations-rail';
import { RunWorkspace } from '@/features/shell/components/run-workspace';
import { StatusStrip } from '@/features/shell/components/status-strip';
import { useKeyboardShortcuts } from '@/features/shell/hooks/use-keyboard-shortcuts';
import { useConnectionStatus } from '@/features/shell/hooks/use-shell-queries';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface CommandCentreShellProps {
  runId?: string;
  incidentId?: string;
  children?: React.ReactNode;
}

function CommandCentreShellInner({ runId, incidentId, children }: CommandCentreShellProps) {
  const resetForRun = useWorkspaceUiStore((state) => state.resetForRun);
  const connectionQuery = useConnectionStatus();
  const liveRun = useLiveRun();
  // A run without page content of its own gets the viewport-height graph workspace; every
  // other shell route (scenarios, reports, admin, after-action) keeps normal page flow.
  const isRunWorkspace = Boolean(runId) && !children;

  useEffect(() => {
    resetForRun(runId ?? null);
  }, [runId, resetForRun]);

  const connectionStatus = connectionQuery.data ?? 'connected';
  const liveHealth = liveRun?.state.connectionHealth;
  const showDisconnectedBanner =
    liveRun?.isLiveMode === true
      ? liveHealth === 'disconnected' ||
        liveHealth === 'reconnecting' ||
        liveHealth === 'stale' ||
        liveHealth === 'gap' ||
        liveRun.state.isStale
      : connectionStatus === 'offline' || connectionStatus === 'reconnecting';

  return (
    <>
      <CommandPalette />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <OperationsRail />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <StatusStrip runId={runId} />
          <ConnectionHealthBanner />
          {showDisconnectedBanner ? (
            <div className="px-5 pt-4 xl:px-6">
              <DisconnectedState
                data-testid="connection-banner"
                message={
                  liveRun?.isLiveMode
                    ? liveHealth === 'reconnecting'
                      ? 'Realtime connection lost. Attempting to reconnect and catch up from the last cursor…'
                      : 'Realtime connection interrupted. Displayed state may be stale until recovery completes.'
                    : connectionStatus === 'offline'
                      ? 'Realtime connection offline. Displaying last known fixture data.'
                      : 'Realtime connection lost. Attempting to reconnect…'
                }
              />
            </div>
          ) : null}
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

export function CommandCentreShell({ runId, incidentId, children }: CommandCentreShellProps) {
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
        <CommandCentreShellInner runId={runId} incidentId={incidentId}>
          {children}
        </CommandCentreShellInner>
      )}
    </div>
  );
}
