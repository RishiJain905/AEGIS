'use client';

import { EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { OperationalGraphView } from '@/features/operational-graph/components/operational-graph-view';
import { useReplay } from '@/features/replay/replay-provider';
import { useReplayStore } from '@/stores/replay-store';

export function ReplayVisualization() {
  const replay = useReplay();
  const state = useReplayStore((store) => store.reconstructedState);
  const loadStatus = useReplayStore((store) => store.loadStatus);
  const errorMessage = useReplayStore((store) => store.errorMessage);
  const errorCode = useReplayStore((store) => store.errorCode);
  const cursor = useReplayStore((store) => store.cursor);

  if (loadStatus === 'loading' && !state) {
    return (
      <Panel title="Operational graph" description="Historical reconstruction" data-testid="visualization-slot">
        <LoadingState message="Loading reconstructed graph…" />
      </Panel>
    );
  }

  if (loadStatus === 'unavailable' || loadStatus === 'error') {
    return (
      <Panel title="Operational graph" description="Historical reconstruction" data-testid="visualization-slot">
        <ErrorState
          message={
            errorMessage ??
            'Replay data is unavailable, corrupted, or incompatible. Live simulation was not mutated.'
          }
        />
        {errorCode ? (
          <p className="mt-2 font-mono text-xs" data-testid="replay-error-code">
            {errorCode}
          </p>
        ) : null}
      </Panel>
    );
  }

  if (!state?.graph || !replay || !cursor) {
    return (
      <Panel title="Operational graph" description="Historical reconstruction" data-testid="visualization-slot">
        <EmptyState
          title="No reconstructed graph"
          description="Scrub the timeline to reconstruct graph state from the Phase 25 replay engine."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Operational graph"
      description={`Historical · sequence ${String(cursor.sequence)}`}
      data-testid="visualization-slot"
    >
      <OperationalGraphView
        runId={replay.runId}
        snapshot={state.graph}
        graphStore={replay.graphStore}
        graphRevision={replay.graphRevision}
      />
    </Panel>
  );
}
