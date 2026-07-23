'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Alert, Badge } from '@aegis/ui';
import type { ReactNode } from 'react';

import { readRunLoadout } from '@/features/command-surface';
import { SitrepButton } from '@/features/comms-desk';
import { LoadoutChips, RoeDial } from '@/features/loadout';
import { ThreatTempoIndicator, useLiveRun } from '@/features/live-run';
import { OperatorIdentityBadge } from '@/features/auth';
import {
  useConnectionStatus,
  useRun,
  useRunReadOnly,
} from '@/features/shell/hooks/use-shell-queries';

interface StatusStripProps {
  runId?: string;
}

function TelemetryItem({
  label,
  value,
  testId,
}: {
  label: string;
  value: ReactNode;
  testId?: string;
}) {
  return (
    <span
      className="flex items-center gap-1.5 border-l border-[var(--aegis-border-subtle)] pl-3 first:border-l-0 first:pl-0 text-[var(--aegis-text-secondary)]"
      data-testid={testId}
    >
      <span className="text-[var(--aegis-text-muted)]">{label}</span>
      <span className="truncate">{value}</span>
    </span>
  );
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
  // The run's actual seed (server-drawn when launched seedless). Surfaced so operators can
  // see and cite the seed for a given run — determinism is anchored to it.
  const seed = runQuery.data?.seed;
  // The run's persisted capability loadout (bias guard, threat tempo, RoE). Absent on legacy
  // runs → chips/dial hidden. The RoE dial edits it mid-run; disabled when the run is read-only.
  const loadout = readRunLoadout(runQuery.data);
  // The run's optional commander's intent (operator priorities set at launch). Surfaced as a
  // compact chip alongside the loadout so it stays visible for the whole engagement.
  const commanderIntent = runQuery.data?.commanderIntent ?? null;

  return (
    <div
      className="sticky top-0 z-30 flex min-h-14 flex-wrap items-center gap-x-4 gap-y-2 border-b border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_78%,transparent)] px-5 py-2.5 backdrop-blur-xl xl:px-6"
      data-testid="status-strip"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2.5">
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
      {runId || runStatus || simTime || sequence !== undefined ? (
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 border-l border-[var(--aegis-border-subtle)] pl-4 font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] leading-4 tabular-nums">
          {runId ? <TelemetryItem label="RUN" value={runId} /> : null}
          {runStatus ? (
            <TelemetryItem label="STATUS" value={runStatus} testId="run-status" />
          ) : null}
          {seed !== undefined ? (
            <TelemetryItem label="SEED" value={seed} testId="run-seed" />
          ) : null}
          {simTime ? <TelemetryItem label="SIM" value={simTime} testId="sim-time" /> : null}
          {sequence !== undefined ? (
            <TelemetryItem label="SEQ" value={sequence} testId="applied-sequence" />
          ) : null}
        </div>
      ) : null}
      {runId && liveRun?.isLiveMode ? <ThreatTempoIndicator runId={runId} /> : null}
      {runId && (loadout || commanderIntent) ? (
        <div className="flex items-center gap-2 border-l border-[var(--aegis-border-subtle)] pl-4">
          <LoadoutChips loadout={loadout} commanderIntent={commanderIntent} />
          {loadout ? <RoeDial runId={runId} current={loadout.roe} disabled={readOnly} /> : null}
        </div>
      ) : null}
      <div className="ml-auto flex items-center gap-2">
        {runId ? <SitrepButton runId={runId} /> : null}
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
