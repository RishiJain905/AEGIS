'use client';

import { Alert, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { GraphDomainHarnessPanel } from '@/features/graph-domain-harness';
import { useRunGraph } from '@/features/shell/hooks/use-shell-queries';

interface VisualizationSlotProps {
  runId: string;
}

export function VisualizationSlot({ runId }: VisualizationSlotProps) {
  const graphQuery = useRunGraph(runId);

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
      description="Sigma.js renderer — Phase 06"
      data-testid="visualization-slot"
      className="min-h-[20rem] flex-1"
    >
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
      <div className="flex min-h-[16rem] flex-col items-center justify-center gap-3 rounded-[var(--aegis-radius-md)] border border-dashed border-[var(--aegis-border-default)] bg-[var(--aegis-surface-base)] p-8 text-center">
        <p className="text-sm font-medium text-[var(--aegis-text-primary)]">
          Graph visualization placeholder
        </p>
        <p className="max-w-md text-sm text-[var(--aegis-text-secondary)]">
          {snapshot.nodes.length} nodes and {snapshot.edges.length} edges loaded from validated
          fixture snapshot (sequence {snapshot.sequence}).
        </p>
        <p className="font-mono text-xs text-[var(--aegis-text-muted)]">
          Primary node: {snapshot.nodes[0]?.label ?? '—'}
        </p>
      </div>
      <GraphDomainHarnessPanel snapshot={snapshot} />
    </Panel>
  );
}
