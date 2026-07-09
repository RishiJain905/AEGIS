'use client';

import { Alert, Badge } from '@aegis/ui';
import { NodeStatus } from '@aegis/contracts-ts';

import { useReplayStore } from '@/stores/replay-store';

export function HistoricalModeBanner() {
  const mode = useReplayStore((state) => state.mode);
  const provenance = useReplayStore((state) => state.provenance);
  const cursor = useReplayStore((state) => state.cursor);
  const loadStatus = useReplayStore((state) => state.loadStatus);

  return (
    <div className="px-4 pt-3" data-testid="historical-mode-banner">
      <Alert
        variant="warning"
        title="Historical replay — read-only"
        className="border-[var(--aegis-border-strong)]"
      >
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge nodeStatus={NodeStatus.UNDER_INVESTIGATION} data-testid="historical-mode-badge">
            {mode === 'playback' ? 'Playback' : 'Historical'}
          </Badge>
          <Badge nodeStatus={NodeStatus.CONTAINED} data-testid="replay-read-only-badge">
            Read-only
          </Badge>
          {cursor ? (
            <span data-testid="replay-cursor-label">
              Cursor sequence {cursor.sequence}
              {cursor.simTime ? ` · sim ${cursor.simTime}` : ''}
            </span>
          ) : null}
          {provenance ? (
            <span data-testid="replay-provenance-label">
              Provenance: {provenance.mode} · applied {provenance.appliedFromSequence}–
              {provenance.appliedToSequence}
            </span>
          ) : null}
          <span className="text-[var(--aegis-text-secondary)]">
            Controls reconstruct historical state. They do not pause, step, or mutate the live
            simulation.
          </span>
          {loadStatus === 'loading' ? <span role="status">Reconstructing…</span> : null}
        </div>
      </Alert>
    </div>
  );
}
