'use client';

import dynamic from 'next/dynamic';

import { Alert, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run';
import { useRunGraph } from '@/features/shell/hooks/use-shell-queries';

const OperationalGraphView = dynamic(
  () =>
    import('@/features/operational-graph').then((mod) => ({
      default: mod.OperationalGraphView,
    })),
  {
    ssr: false,
    loading: () => (
      <div
        className="flex min-h-[16rem] items-center justify-center text-sm text-[var(--aegis-text-secondary)]"
        data-testid="operational-graph-loading"
      >
        Initializing graph renderer…
      </div>
    ),
  },
);

interface VisualizationSlotProps {
  runId: string;
  incidentId?: string;
}

export function VisualizationSlot({ runId, incidentId }: VisualizationSlotProps) {
  const liveRun = useLiveRun();
  const graphQuery = useRunGraph(runId, {
    enabled: liveRun?.isLiveMode !== true,
  });

  if (liveRun?.isLiveMode && liveRun.bootstrapSnapshot) {
    return (
      <Panel
        title="Operational graph"
        description="Live Sigma.js operational investigation graph"
        data-testid="visualization-slot"
      >
        <OperationalGraphView
          runId={runId}
          incidentId={incidentId}
          snapshot={liveRun.bootstrapSnapshot}
          graphStore={liveRun.graphStore}
          graphRevision={liveRun.graphRevision}
        />
      </Panel>
    );
  }

  if (graphQuery.isPending) {
    return (
      <Panel title="Operational graph" data-testid="visualization-slot">
        <LoadingState message="Loading graph projection…" />
      </Panel>
    );
  }

  if (graphQuery.isError) {
    return (
      <Panel title="Operational graph" data-testid="visualization-slot">
        <ErrorState
          message="Unable to load graph projection."
          onRetry={() => void graphQuery.refetch()}
        />
      </Panel>
    );
  }

  const { snapshot, partial } = graphQuery.data;

  if (!snapshot) {
    return (
      <Panel title="Operational graph" data-testid="visualization-slot">
        {partial ? (
          <Alert
            variant="warning"
            title="Partial graph data"
            className="mb-4"
            data-testid="partial-graph-alert"
          >
            Graph snapshot is incomplete. Additional nodes and edges arrive in later phases.
          </Alert>
        ) : null}
        <EmptyState
          title="Graph unavailable"
          description="No graph snapshot is available for this run yet."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Operational graph"
      description="Sigma.js operational investigation graph"
      data-testid="visualization-slot"
    >
      <OperationalGraphView runId={runId} incidentId={incidentId} snapshot={snapshot} />
    </Panel>
  );
}
