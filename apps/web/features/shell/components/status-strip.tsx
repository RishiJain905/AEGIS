'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Alert, Badge } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run';
import { OperatorIdentityBadge } from '@/features/auth';
import {
  useConnectionStatus,
  useRun,
  useRunReadOnly,
} from '@/features/shell/hooks/use-shell-queries';

interface StatusStripProps {
  runId?: string;
}

const LIVE_HEALTH_LABELS: Record<string, string> = {
  connected: 'Live',
  disconnected: 'Offline',
  reconnecting: 'Reconnecting',
  catching_up: 'Catching up',
  gap: 'Gap',
  snapshot_resync: 'Resyncing',
  simulator_paused: 'Sim paused',
  locally_paused: 'Updates paused',
  stale: 'Stale',
};

export function StatusStrip({ runId }: StatusStripProps) {
  const connectionQuery = useConnectionStatus();
  const runQuery = useRun(runId ?? '');
  const readOnlyQuery = useRunReadOnly(runId ?? '');
  const liveRun = useLiveRun();

  const connectionStatus = connectionQuery.data ?? 'connected';
  const readOnly = readOnlyQuery.data ?? false;

  const connectionLabel =
    liveRun?.isLiveMode === true
      ? (LIVE_HEALTH_LABELS[liveRun.state.connectionHealth] ?? liveRun.state.connectionHealth)
      : connectionStatus === 'offline'
        ? 'Offline'
        : connectionStatus === 'reconnecting'
          ? 'Reconnecting'
          : 'Connected';

  const runStatus = liveRun?.isLiveMode ? liveRun.state.runStatus : runQuery.data?.status;
  const simTime = liveRun?.isLiveMode ? liveRun.state.simTime : runQuery.data?.simTime;
  const sequence = liveRun?.isLiveMode ? liveRun.state.lastAppliedSequence : undefined;

  return (
    <div
      className="flex flex-wrap items-center gap-3 border-b border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] px-4 py-2"
      data-testid="status-strip"
      role="status"
      aria-live="polite"
    >
      <Badge
        nodeStatus={
          connectionLabel === 'Live' || connectionLabel === 'Connected'
            ? NodeStatus.NORMAL
            : NodeStatus.SUSPICIOUS
        }
        data-testid="connection-status-badge"
      >
        {connectionLabel}
      </Badge>
      {readOnly ? (
        <Badge nodeStatus={NodeStatus.UNDER_INVESTIGATION} data-testid="read-only-badge">
          Read-only
        </Badge>
      ) : null}
      {runId ? (
        <span className="font-mono text-xs text-[var(--aegis-text-secondary)]">Run: {runId}</span>
      ) : null}
      {runStatus ? (
        <span className="text-xs text-[var(--aegis-text-secondary)]" data-testid="run-status">
          Status: {runStatus}
        </span>
      ) : null}
      {simTime ? (
        <span className="text-xs text-[var(--aegis-text-secondary)]" data-testid="sim-time">
          Sim time: {simTime}
        </span>
      ) : null}
      {sequence !== undefined ? (
        <span className="text-xs text-[var(--aegis-text-secondary)]" data-testid="applied-sequence">
          Sequence: {sequence}
        </span>
      ) : null}
      <div className="ml-auto">
        <OperatorIdentityBadge />
      </div>
      {!liveRun?.isLiveMode && connectionStatus === 'offline' ? (
        <Alert variant="warning" title="Connection offline" className="max-w-md">
          Realtime updates are unavailable. Showing last known fixture data.
        </Alert>
      ) : null}
      {!liveRun?.isLiveMode && connectionStatus === 'reconnecting' ? (
        <Alert variant="default" title="Reconnecting" className="ml-auto max-w-md">
          Attempting to restore realtime connection…
        </Alert>
      ) : null}
      {liveRun?.isLiveMode && liveRun.state.isStale ? (
        <Alert variant="warning" title="State may be stale" className="ml-auto max-w-md">
          Event delivery is interrupted. Recovery is required before trusting the live view.
        </Alert>
      ) : null}
    </div>
  );
}
