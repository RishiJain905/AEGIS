'use client';

import { DisconnectedState } from '@aegis/ui';
import { useEffect } from 'react';

import { AgentChatPanel } from '@/features/agent-chat';
import {
  ConnectionHealthBanner,
  LiveRunControls,
  LiveRunProvider,
  useLiveRun,
} from '@/features/live-run';
import { OpsFeedPanel } from '@/features/ops-feed';
import { OperatorConsolePanel } from '@/features/operator-console';
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
            className="flex min-h-0 flex-1 flex-col gap-5 p-5 xl:flex-row xl:gap-6 xl:p-6"
          >
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
              <LiveRunControls />
              {children ? (
                children
              ) : runId ? (
                /*
                  Command surface: the operational graph is the centerpiece, flanked by the AI
                  copilot (steering channel, left) and the ops feed (live heartbeat, right). The
                  operator console docks beneath the graph. Flanks stack above/below the graph
                  until there is room to sit beside it (2xl), so the layout stays legible on a
                  laptop and opens up on an ops-room display.
                */
                <div className="flex min-h-0 flex-col gap-4 2xl:flex-row 2xl:items-start">
                  <div className="flex min-w-0 flex-col gap-4 2xl:w-[21rem] 2xl:shrink-0">
                    <AgentChatPanel runId={runId} />
                  </div>
                  <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
                    <VisualizationSlot runId={runId} incidentId={incidentId} />
                    <OperatorConsolePanel runId={runId} />
                  </div>
                  <div className="flex min-w-0 flex-col gap-4 2xl:w-[22rem] 2xl:shrink-0">
                    <OpsFeedPanel runId={runId} />
                  </div>
                </div>
              ) : null}
              <TimelineView />
            </div>
            <InspectorPanel runId={runId} incidentId={incidentId} />
          </main>
        </div>
      </div>
    </>
  );
}

export function CommandCentreShell({ runId, incidentId, children }: CommandCentreShellProps) {
  useKeyboardShortcuts();

  return (
    <div
      className="aegis-command-shell flex min-h-screen flex-col"
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
