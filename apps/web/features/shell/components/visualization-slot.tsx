'use client';

import dynamic from 'next/dynamic';

import {
  Alert,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
  cn,
  typographyTokens,
} from '@aegis/ui';

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
        className="flex min-h-[16rem] flex-1 items-center justify-center text-sm text-[var(--aegis-text-secondary)]"
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
        className="flex min-h-[16rem] flex-1 items-center justify-center text-sm text-[var(--aegis-text-secondary)]"
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

/**
 * The stage header: one line, because everything it used to say in three was chrome
 * competing with the map for height. The 2D/3D switch lives here rather than inside either
 * renderer so it stays in the same place across modes, and the sync indicator shares its
 * instrument styling so the pair reads as one designed control.
 */
function StageFrame({
  title,
  hint,
  scroll = false,
  children,
}: {
  title: string;
  hint: string;
  /** 3D is a fixed-height presentation; let it scroll instead of squashing the stage. */
  scroll?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      data-testid="visualization-slot"
      className="flex min-h-0 flex-1 flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className={cn(typographyTokens.displayMd, 'text-[var(--aegis-text-primary)]')}>
          {title}
        </h2>
        <p className="hidden truncate font-[family-name:var(--aegis-font-mono)] text-[0.625rem] uppercase tracking-[0.1em] text-[var(--aegis-text-faint)] lg:block">
          {hint}
        </p>
        <div className="ml-auto flex items-stretch gap-2">
          <span
            data-testid="graph-sync-chip"
            title="This view is projected from the synchronized graph store; both renderers read the same state."
            className="flex items-center gap-1.5 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-canvas)] px-2.5 font-[family-name:var(--aegis-font-mono)] text-[0.625rem] uppercase tracking-[0.1em] text-[var(--aegis-text-muted)] shadow-[inset_0_1px_5px_rgb(0_0_0_/_0.28)]"
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-[var(--aegis-status-normal)]"
            />
            Graph synced
          </span>
          <GraphViewModeToggle />
        </div>
      </div>
      <div
        className={cn(
          'flex min-h-0 flex-1 flex-col',
          scroll ? 'overflow-y-auto' : 'overflow-hidden',
        )}
      >
        {children}
      </div>
    </section>
  );
}

export function VisualizationSlot({ runId, incidentId }: VisualizationSlotProps) {
  const liveRun = useLiveRun();
  const graphQuery = useRunGraph(runId, {
    enabled: liveRun?.isLiveMode !== true,
  });
  const viewMode = useCinematicGraphStore((s) => s.viewMode);
  const isThreeD = viewMode === GraphViewMode.THREE_D;

  if (liveRun?.isLiveMode && liveRun.bootstrapSnapshot) {
    return (
      <StageFrame
        title={isThreeD ? 'Semantic 3D graph' : 'Operational graph'}
        hint={
          isThreeD
            ? 'Read-only semantic presentation of live command-centre state'
            : 'Live analysis plane — authoritative for investigation'
        }
        scroll={isThreeD}
      >
        <RevealAnnouncer nodes={liveRun.bootstrapSnapshot.nodes} revision={liveRun.graphRevision} />
        {isThreeD ? (
          <CinematicGraphView
            runId={runId}
            snapshot={liveRun.bootstrapSnapshot}
            graphStore={liveRun.graphStore}
            graphRevision={liveRun.graphRevision}
            liveSequence={liveRun.state.lastAppliedSequence}
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
      </StageFrame>
    );
  }

  if (graphQuery.isPending) {
    return (
      <Panel title="Operational graph" data-testid="visualization-slot" className="flex-1">
        <LoadingState message="Loading graph projection…" />
      </Panel>
    );
  }

  if (graphQuery.isError) {
    return (
      <Panel title="Operational graph" data-testid="visualization-slot" className="flex-1">
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
      <Panel title="Operational graph" data-testid="visualization-slot" className="flex-1">
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
    <StageFrame
      title={isThreeD ? 'Semantic 3D graph' : 'Operational graph'}
      hint={
        isThreeD
          ? 'Read-only semantic presentation over the same GraphStore'
          : 'Analysis plane — authoritative for investigation'
      }
      scroll={isThreeD}
    >
      {isThreeD ? (
        <CinematicGraphView runId={runId} snapshot={snapshot} />
      ) : (
        <OperationalGraphView runId={runId} incidentId={incidentId} snapshot={snapshot} />
      )}
    </StageFrame>
  );
}
