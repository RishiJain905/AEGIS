'use client';

import dynamic from 'next/dynamic';

import { EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { GraphViewModeToggle, useCinematicGraphStore } from '@/features/cinematic-graph';
import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useReplay } from '@/features/replay/replay-provider';
import { useReplayStore } from '@/stores/replay-store';

const OperationalGraphView = dynamic(
  () =>
    import('@/features/operational-graph/components/operational-graph-view').then(
      (module) => module.OperationalGraphView,
    ),
  {
    ssr: false,
    loading: () => <LoadingState message="Loading historical graph renderer…" />,
  },
);

const CinematicGraphView = dynamic(
  () => import('@/features/cinematic-graph').then((module) => module.CinematicGraphView),
  {
    ssr: false,
    loading: () => <LoadingState message="Loading historical 3D semantic renderer…" />,
  },
);

export function ReplayVisualization() {
  const replay = useReplay();
  const state = useReplayStore((store) => store.reconstructedState);
  const loadStatus = useReplayStore((store) => store.loadStatus);
  const errorMessage = useReplayStore((store) => store.errorMessage);
  const errorCode = useReplayStore((store) => store.errorCode);
  const cursor = useReplayStore((store) => store.cursor);
  const viewMode = useCinematicGraphStore((store) => store.viewMode);

  if (loadStatus === 'loading' && !state) {
    return (
      <Panel
        title="Operational graph"
        description="Historical reconstruction"
        data-testid="visualization-slot"
      >
        <LoadingState message="Loading reconstructed graph…" />
      </Panel>
    );
  }

  if (loadStatus === 'unavailable' || loadStatus === 'error') {
    return (
      <Panel
        title="Operational graph"
        description="Historical reconstruction"
        data-testid="visualization-slot"
      >
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
      <Panel
        title="Operational graph"
        description="Historical reconstruction"
        data-testid="visualization-slot"
      >
        <EmptyState
          title="No reconstructed graph"
          description="Scrub the timeline to reconstruct graph state from the Phase 25 replay engine."
        />
      </Panel>
    );
  }

  const evidenceNodeIds = state.evidence
    .map((item) => item.assetId)
    .filter((id): id is string => typeof id === 'string' && id.length > 0);
  const incidentNodeIds = state.graph.nodes
    .filter(
      (node) =>
        node.status === 'under_investigation' ||
        node.status === 'compromised' ||
        node.status === 'contained',
    )
    .map((node) => node.id);

  return (
    <Panel
      title={viewMode === GraphViewMode.THREE_D ? 'Semantic 3D graph' : 'Operational graph'}
      description={
        viewMode === GraphViewMode.THREE_D
          ? `Historical 3D · sequence ${String(cursor.sequence)}`
          : `Historical · sequence ${String(cursor.sequence)}`
      }
      data-testid="visualization-slot"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          2D and 3D share the same reconstructed GraphStore at this replay cursor.
        </p>
        <GraphViewModeToggle />
      </div>
      {viewMode === GraphViewMode.THREE_D ? (
        <CinematicGraphView
          runId={replay.runId}
          snapshot={state.graph}
          graphStore={replay.graphStore}
          graphRevision={replay.graphRevision}
          evidenceNodeIds={evidenceNodeIds}
          incidentNodeIds={incidentNodeIds}
        />
      ) : (
        <OperationalGraphView
          runId={replay.runId}
          snapshot={state.graph}
          graphStore={replay.graphStore}
          graphRevision={replay.graphRevision}
        />
      )}
    </Panel>
  );
}
