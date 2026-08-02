'use client';

import { useMemo } from 'react';

import { NodeStatus } from '@aegis/contracts-ts';
import { Badge } from '@aegis/ui';
import type { ReactNode } from 'react';

import { readRunLoadout } from '@/features/command-surface';
import { SitrepButton } from '@/features/comms-desk';
import { LoadoutChips, RoeDial } from '@/features/loadout';
import { ThreatTempoIndicator, useLiveRun } from '@/features/live-run';
import { OperatorIdentityBadge } from '@/features/auth';
import { useAfterActionReport } from '@/features/reports/use-report-queries';
import { RunStatusRail } from '@/features/shell/components/run-status-rail';
import {
  useConnectionStatus,
  useRun,
  useRunGraph,
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

export function StatusStrip({ runId }: StatusStripProps) {
  const connectionQuery = useConnectionStatus();
  const runQuery = useRun(runId ?? '');
  const readOnlyQuery = useRunReadOnly(runId ?? '');
  const liveRun = useLiveRun();
  const isLiveMode = liveRun?.isLiveMode === true;

  const connectionStatus = connectionQuery.data ?? 'connected';
  const readOnly = readOnlyQuery.data ?? false;

  const runStatus = isLiveMode ? liveRun.state.runStatus : runQuery.data?.status;
  const simTime = isLiveMode ? liveRun.state.simTime : runQuery.data?.simTime;
  const sequence = isLiveMode ? liveRun.state.lastAppliedSequence : undefined;
  // The run's actual seed (server-drawn when launched seedless). Surfaced so operators can
  // see and cite the seed for a given run — determinism is anchored to it.
  const seed = runQuery.data?.seed;
  // The run's persisted capability loadout (bias guard, threat tempo, RoE). Absent on legacy
  // runs → chips/dial hidden. The RoE dial edits it mid-run; disabled when the run is read-only.
  const loadout = readRunLoadout(runQuery.data);
  // The run's optional commander's intent (operator priorities set at launch). Surfaced as a
  // compact chip alongside the loadout so it stays visible for the whole engagement.
  const commanderIntent = runQuery.data?.commanderIntent ?? null;

  // Posture is the worst *disclosed* node status. Live runs read the mutable graph store
  // (revision-keyed so a status delta re-derives it); fixture views read the REST snapshot.
  const restGraphQuery = useRunGraph(runId ?? '', { enabled: Boolean(runId) && !isLiveMode });
  const graphRevision = isLiveMode ? liveRun.graphRevision : 0;
  const liveGraphStore =
    liveRun !== null && liveRun.isLiveMode && liveRun.bootstrapSnapshot !== null
      ? liveRun.graphStore
      : null;
  const postureNodes = useMemo(() => {
    if (liveGraphStore !== null) {
      return liveGraphStore.exportSnapshot().nodes;
    }
    return restGraphQuery.data?.snapshot?.nodes ?? undefined;
  }, [liveGraphStore, graphRevision, restGraphQuery.data]);

  // Report readiness: only queried once the run is terminal (the hook itself never fires
  // before that thanks to `enabled`), so the chip is honest about "ended but not written".
  const terminal = runStatus === 'completed' || runStatus === 'stopped';
  const reportQuery = useAfterActionReport(runId ?? '', { enabled: Boolean(runId) && terminal });

  return (
    <div
      className="sticky top-0 z-30 flex min-h-14 flex-wrap items-center gap-x-4 gap-y-2 border-b border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_78%,transparent)] px-5 py-2.5 backdrop-blur-xl xl:px-6"
      data-testid="status-strip"
      role="status"
      aria-live="polite"
    >
      <RunStatusRail
        isLiveMode={isLiveMode}
        connectionHealth={isLiveMode ? liveRun.state.connectionHealth : undefined}
        connectionStatus={connectionStatus}
        runStatus={runStatus}
        nodes={postureNodes}
        reportAvailable={reportQuery.data !== undefined}
        hasRun={Boolean(runId)}
      />
      {readOnly ? (
        <Badge nodeStatus={NodeStatus.UNDER_INVESTIGATION} data-testid="read-only-badge">
          Read-only
        </Badge>
      ) : null}
      {runId || simTime || sequence !== undefined ? (
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 border-l border-[var(--aegis-border-subtle)] pl-4 font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] leading-4 tabular-nums">
          {runId ? <TelemetryItem label="RUN" value={runId} /> : null}
          {seed !== undefined ? (
            <TelemetryItem label="SEED" value={seed} testId="run-seed" />
          ) : null}
          {simTime ? <TelemetryItem label="CLOCK" value={simTime} testId="sim-time" /> : null}
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
    </div>
  );
}
