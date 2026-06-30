'use client';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { Badge, Panel } from '@aegis/ui';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';

export interface GraphEntityInspectorProps {
  snapshot: GraphSnapshotV1;
  selectedEntityId: string | null;
}

export function GraphEntityInspector({ snapshot, selectedEntityId }: GraphEntityInspectorProps) {
  const visualState = useGraphVisualStore((s) => s.visualState);

  if (!selectedEntityId) {
    return null;
  }

  const node = snapshot.nodes.find((n) => n.id === selectedEntityId);
  if (!node) {
    return null;
  }

  const pathNodes = visualState.highlightedNodeIds;
  const showPath = visualState.highlightMode === 'path' && pathNodes.length > 0;

  return (
    <Panel title="Asset" density="compact" data-testid="graph-entity-inspector">
      <p className="text-sm font-medium">{node.label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Badge>{node.assetType}</Badge>
        <Badge>{node.status.replace(/_/g, ' ')}</Badge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Risk score</dt>
          <dd className="font-mono">{node.riskScore.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Criticality</dt>
          <dd className="font-mono">{node.criticality.toFixed(2)}</dd>
        </div>
        {node.clusterId ? (
          <div className="col-span-2">
            <dt className="text-[var(--aegis-text-muted)]">Cluster</dt>
            <dd className="font-mono">{node.clusterId}</dd>
          </div>
        ) : null}
      </dl>
      <p className="mt-2 font-mono text-xs text-[var(--aegis-text-muted)]">{node.id}</p>

      {showPath ? (
        <div
          className="mt-4 border-t border-[var(--aegis-border-subtle)] pt-3"
          data-testid="path-inspector-section"
        >
          <p className="text-xs font-semibold text-[var(--aegis-text-muted)]">Highlighted path</p>
          <p className="mt-1 font-mono text-xs">{pathNodes.join(' → ')}</p>
        </div>
      ) : null}
    </Panel>
  );
}
