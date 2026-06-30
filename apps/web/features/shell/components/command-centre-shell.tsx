'use client';

import { DisconnectedState } from '@aegis/ui';
import { useEffect } from 'react';

import { CommandPalette } from '@/features/shell/components/command-palette';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { OperationsRail } from '@/features/shell/components/operations-rail';
import { StatusStrip } from '@/features/shell/components/status-strip';
import { TimelineArea } from '@/features/shell/components/timeline-area';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { useKeyboardShortcuts } from '@/features/shell/hooks/use-keyboard-shortcuts';
import { useConnectionStatus } from '@/features/shell/hooks/use-shell-queries';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface CommandCentreShellProps {
  runId?: string;
  incidentId?: string;
  children?: React.ReactNode;
}

export function CommandCentreShell({ runId, incidentId, children }: CommandCentreShellProps) {
  useKeyboardShortcuts();
  const resetForRun = useWorkspaceUiStore((state) => state.resetForRun);
  const connectionQuery = useConnectionStatus();

  useEffect(() => {
    resetForRun(runId ?? null);
  }, [runId, resetForRun]);

  const connectionStatus = connectionQuery.data ?? 'connected';

  return (
    <div
      className="flex min-h-screen flex-col bg-[var(--aegis-surface-base)]"
      data-testid="command-centre-shell"
    >
      <CommandPalette />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <OperationsRail />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <StatusStrip runId={runId} />
          {connectionStatus === 'offline' || connectionStatus === 'reconnecting' ? (
            <div className="px-4 pt-3">
              <DisconnectedState
                data-testid="connection-banner"
                message={
                  connectionStatus === 'offline'
                    ? 'Realtime connection offline. Displaying last known fixture data.'
                    : 'Realtime connection lost. Attempting to reconnect…'
                }
              />
            </div>
          ) : null}
          <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 xl:flex-row">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
              {children ?? (runId ? <VisualizationSlot runId={runId} /> : null)}
              <TimelineArea />
            </div>
            <InspectorPanel runId={runId} incidentId={incidentId} />
          </div>
        </div>
      </div>
    </div>
  );
}
