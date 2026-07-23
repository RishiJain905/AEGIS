'use client';

import dynamic from 'next/dynamic';

import { Alert, Badge, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { GraphViewModeToggle, useCinematicGraphStore } from '@/features/cinematic-graph';
import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useLiveRun } from '@/features/live-run';
import { RevealAnnouncer } from '@/features/operational-graph';
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

const CinematicGraphView = dynamic(
  () =>
    import('@/features/cinematic-graph').then((mod) => ({
      default: mod.CinematicGraphView,
    })),
  {
    ssr: false,
    loading: () => (
      <div
        className="flex min-h-[16rem] items-center justify-center text-sm text-[var(--aegis-text-secondary)]"
        data-testid="cinematic-graph-loading"
      >
        Initializing 3D semantic renderer…
      </div>
    ),
  },
);

interface VisualizationSlotProps {
  runId: string;
  incidentId?: string;
}

function GraphPanelChrome({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Panel
      title={title}
      description={description}
      density="compact"
      data-testid="visualization-slot"
    >
      <div className="mb-4 flex flex-col gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] p-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2.5">
          <Badge variant="outline">GraphStore synced</Badge>
          <p className="text-xs leading-5 text-[var(--aegis-text-secondary)]">
            2D analysis is authoritative; 3D is the read-only semantic presentation.
          </p>
        </div>
        <GraphViewModeToggle />
      </div>
      {children}
    </Panel>
  );
}

export function VisualizationSlot({ runId, incidentId }: VisualizationSlotProps) {
  const liveRun = useLiveRun();
  const graphQuery = useRunGraph(runId, {
    enabled: liveRun?.isLiveMode !== true,
  });
  const viewMode = useCinematicGraphStore((s) => s.viewMode);

  if (liveRun?.isLiveMode && liveRun.bootstrapSnapshot) {
    return (
      <GraphPanelChrome
        title={viewMode === GraphViewMode.THREE_D ? 'Semantic 3D graph' : 'Operational graph'}
        description={
          viewMode === GraphViewMode.THREE_D
            ? 'Three.js semantic presentation of live command-centre graph state'
            : 'Live Sigma.js operational investigation graph'
        }
      >
        <RevealAnnouncer nodes={liveRun.bootstrapSnapshot.nodes} revision={liveRun.graphRevision} />
        {viewMode === GraphViewMode.THREE_D ? (
          <CinematicGraphView
            runId={runId}
            snapshot={liveRun.bootstrapSnapshot}
            graphStore={liveRun.graphStore}
            graphRevision={liveRun.graphRevision}
          />
        ) : (
          <OperationalGraphView
            runId={runId}
            incidentId={incidentId}
            snapshot={liveRun.bootstrapSnapshot}
            graphStore={liveRun.graphStore}
            graphRevision={liveRun.graphRevision}
          />
        )}
      </GraphPanelChrome>
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
    <GraphPanelChrome
      title={viewMode === GraphViewMode.THREE_D ? 'Semantic 3D graph' : 'Operational graph'}
      description={
        viewMode === GraphViewMode.THREE_D
          ? 'Three.js semantic presentation over the same GraphStore as Sigma.js'
          : 'Sigma.js operational investigation graph'
      }
    >
      {viewMode === GraphViewMode.THREE_D ? (
        <CinematicGraphView runId={runId} snapshot={snapshot} />
      ) : (
        <OperationalGraphView runId={runId} incidentId={incidentId} snapshot={snapshot} />
      )}
    </GraphPanelChrome>
  );
}
