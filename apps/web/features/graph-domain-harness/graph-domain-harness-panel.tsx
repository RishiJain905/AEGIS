'use client';

import { useMemo } from 'react';

import { createGraphStore, GraphLayer } from '@aegis/graph-domain';
import { MetricTile, Panel } from '@aegis/ui';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';

interface GraphDomainHarnessPanelProps {
  snapshot: GraphSnapshotV1;
}

export function GraphDomainHarnessPanel({ snapshot }: GraphDomainHarnessPanelProps) {
  const analysis = useMemo(() => {
    const store = createGraphStore();
    store.loadSnapshot(snapshot);

    const consistency = store.validateConsistency();
    const pathQuery = store.queryPaths({
      schemaVersion: 1,
      runId: snapshot.runId,
      sourceId: snapshot.nodes[0]?.id ?? 'asset:unknown',
      targetId: snapshot.nodes[0]?.id ?? 'asset:unknown',
      maxHops: 4,
      relationshipTypes: [],
      directedOnly: true,
    });

    const centerNodeId =
      snapshot.nodes[0]?.id ?? snapshot.edges[0]?.source ?? snapshot.edges[0]?.target ?? null;

    const neighborhood =
      centerNodeId !== null
        ? store.getNeighborhood(centerNodeId, { hops: 1 })
        : { nodeIds: [], edgeIds: [], hopRings: [], explanation: {} };

    const filtered = store.applyFilters({
      enabledLayers: [
        GraphLayer.INFRASTRUCTURE,
        GraphLayer.ACTIVITY,
        GraphLayer.SECURITY_STATE,
        GraphLayer.INVESTIGATION,
        GraphLayer.PRESENTATION,
      ],
    });

    const deltaReplay = store.applyDelta({
      schemaVersion: 1,
      runId: snapshot.runId,
      sequence: snapshot.sequence,
      revision: snapshot.revision,
      operation: 'upsert_node',
      node: snapshot.nodes[0]
        ? {
            ...snapshot.nodes[0],
            revision: snapshot.nodes[0].revision,
          }
        : undefined,
    });

    const pathsConsidered =
      typeof pathQuery.explanation.pathsConsidered === 'number'
        ? pathQuery.explanation.pathsConsidered
        : 0;

    return {
      consistency,
      pathQuery,
      neighborhood,
      filtered,
      deltaReplay,
      components: store.getConnectedComponents().length,
      pathsConsidered,
    };
  }, [snapshot]);

  return (
    <Panel
      title="Graph domain engine"
      description="Phase 05 — renderer-independent analysis harness"
      data-testid="graph-domain-harness"
      className="mt-4"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          label="Consistency"
          value={analysis.consistency.valid ? 'Valid' : 'Issues'}
          trend={`${String(analysis.consistency.nodeCount)} nodes · ${String(analysis.consistency.edgeCount)} edges`}
        />
        <MetricTile
          label="Paths found"
          value={String(analysis.pathQuery.paths.length)}
          trend={`Considered ${String(analysis.pathsConsidered)}`}
        />
        <MetricTile
          label="1-hop neighborhood"
          value={String(analysis.neighborhood.nodeIds.length)}
          trend={`${String(analysis.neighborhood.edgeIds.length)} edges`}
        />
        <MetricTile
          label="Components"
          value={String(analysis.components)}
          trend={`${String(analysis.filtered.visibleNodeIds.length)} visible nodes`}
        />
      </div>
      <p
        className="mt-4 text-sm text-[var(--aegis-text-secondary)]"
        data-testid="graph-domain-delta-status"
      >
        Delta replay status: {analysis.deltaReplay.status} (sequence{' '}
        {String(analysis.deltaReplay.sequence)})
      </p>
      {analysis.pathQuery.paths[0] ? (
        <p
          className="mt-2 font-mono text-xs text-[var(--aegis-text-muted)]"
          data-testid="graph-domain-path"
        >
          Sample path: {analysis.pathQuery.paths[0].join(' → ')}
        </p>
      ) : (
        <p className="mt-2 text-xs text-[var(--aegis-text-muted)]" data-testid="graph-domain-path">
          No path between selected endpoints in current snapshot.
        </p>
      )}
    </Panel>
  );
}
