'use client';

import { DisconnectedState } from '@aegis/ui';
import { useEffect } from 'react';

import {
  ConnectionHealthBanner,
  LiveRunControls,
  LiveRunProvider,
  useLiveRun,
} from '@/features/live-run';
import { CommandPalette } from '@/features/shell/components/command-palette';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { OperationsRail } from '@/features/shell/components/operations-rail';
import { StatusStrip } from '@/features/shell/components/status-strip';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { useKeyboardShortcuts } from '@/features/shell/hooks/use-keyboard-shortcuts';
import { useConnectionStatus } from '@/features/shell/hooks/use-shell-queries';
import { TimelineView } from '@/features/timeline';
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
            <div className="px-4 pt-3">
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
          <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 xl:flex-row">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
              <LiveRunControls />
              {children ?? (runId ? <VisualizationSlot runId={runId} /> : null)}
              <TimelineView />
            </div>
            <InspectorPanel runId={runId} incidentId={incidentId} />
          </div>
        </div>
      </div>
    </>
  );
}

export function CommandCentreShell({ runId, incidentId, children }: CommandCentreShellProps) {
  useKeyboardShortcuts();

  return (
    <div
      className="flex min-h-screen flex-col bg-[var(--aegis-surface-base)]"
      data-testid="command-centre-shell"
    >
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
