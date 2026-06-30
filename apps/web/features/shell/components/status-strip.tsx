'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Alert, Badge } from '@aegis/ui';

import {
  useConnectionStatus,
  useRun,
  useRunReadOnly,
} from '@/features/shell/hooks/use-shell-queries';

interface StatusStripProps {
  runId?: string;
}

export function StatusStrip({ runId }: StatusStripProps) {
  const connectionQuery = useConnectionStatus();
  const runQuery = useRun(runId ?? '');
  const readOnlyQuery = useRunReadOnly(runId ?? '');

  const connectionStatus = connectionQuery.data ?? 'connected';
  const readOnly = readOnlyQuery.data ?? false;

  const connectionLabel =
    connectionStatus === 'offline'
      ? 'Offline'
      : connectionStatus === 'reconnecting'
        ? 'Reconnecting'
        : 'Connected';

  return (
    <div
      className="flex flex-wrap items-center gap-3 border-b border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] px-4 py-2"
      data-testid="status-strip"
      role="status"
      aria-live="polite"
    >
      <Badge
        nodeStatus={connectionStatus === 'connected' ? NodeStatus.NORMAL : NodeStatus.SUSPICIOUS}
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
      {runQuery.data ? (
        <span className="text-xs text-[var(--aegis-text-secondary)]">
          Sim time: {runQuery.data.simTime}
        </span>
      ) : null}
      {connectionStatus === 'offline' ? (
        <Alert variant="warning" title="Connection offline" className="ml-auto max-w-md">
          Realtime updates are unavailable. Showing last known fixture data.
        </Alert>
      ) : null}
      {connectionStatus === 'reconnecting' ? (
        <Alert variant="default" title="Reconnecting" className="ml-auto max-w-md">
          Attempting to restore realtime connection…
        </Alert>
      ) : null}
    </div>
  );
}
