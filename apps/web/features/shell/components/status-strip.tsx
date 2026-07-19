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
      className="sticky top-0 z-30 flex min-h-14 flex-wrap items-center gap-x-4 gap-y-2 border-b border-[var(--aegis-border-default)] bg-[color-mix(in_srgb,var(--aegis-surface-rail)_95%,transparent)] px-4 py-2 shadow-[0_8px_24px_rgb(0_0_0_/_0.2)] backdrop-blur-md"
      data-testid="status-strip"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2.5 border-r border-[var(--aegis-border-subtle)] pr-4">
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.6875rem] font-semibold uppercase tracking-[0.13em] text-[var(--aegis-text-muted)]">
          Control link
        </span>
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
      </div>
      {readOnly ? (
        <Badge nodeStatus={NodeStatus.UNDER_INVESTIGATION} data-testid="read-only-badge">
          Read-only
        </Badge>
      ) : null}
      {runId ? (
        <span className="font-mono text-[0.6875rem] text-[var(--aegis-text-secondary)] tabular-nums">
          <span className="text-[var(--aegis-text-muted)]">RUN</span> {runId}
        </span>
      ) : null}
      {runStatus ? (
        <span className="text-xs text-[var(--aegis-text-secondary)]" data-testid="run-status">
          <span className="text-[var(--aegis-text-muted)]">Status</span> {runStatus}
        </span>
      ) : null}
      {simTime ? (
        <span
          className="font-mono text-[0.6875rem] text-[var(--aegis-text-secondary)] tabular-nums"
          data-testid="sim-time"
        >
          <span className="text-[var(--aegis-text-muted)]">SIM</span> {simTime}
        </span>
      ) : null}
      {sequence !== undefined ? (
        <span
          className="font-mono text-[0.6875rem] text-[var(--aegis-text-secondary)] tabular-nums"
          data-testid="applied-sequence"
        >
          <span className="text-[var(--aegis-text-muted)]">SEQ</span> {sequence}
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
