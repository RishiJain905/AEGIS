'use client';

import type { AssetRiskScoreV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import { Badge, Panel } from '@aegis/ui';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';

import {
  InspectorField,
  InspectorLabel,
  InspectorMetric,
  InspectorMetricGrid,
  InspectorMonoBlock,
  InspectorMonoValue,
} from './inspector-primitives';

export interface GraphEntityInspectorProps {
  snapshot: GraphSnapshotV1;
  selectedEntityId: string | null;
  riskScore?: AssetRiskScoreV1 | null;
}

export function GraphEntityInspector({
  snapshot,
  selectedEntityId,
  riskScore,
}: GraphEntityInspectorProps) {
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
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold leading-5 text-[var(--aegis-text-primary)]">
            {node.label}
          </p>
          <div className="flex flex-wrap gap-2">
            <Badge>{node.assetType}</Badge>
            <Badge variant="outline">{node.status.replace(/_/g, ' ')}</Badge>
          </div>
        </div>

        <InspectorMetricGrid>
          <InspectorMetric
            label="Risk score"
            value={(riskScore?.total ?? node.riskScore).toFixed(2)}
          />
          <InspectorMetric label="Criticality" value={node.criticality.toFixed(2)} />
          {riskScore ? (
            <>
              <InspectorMetric label="Direct" value={riskScore.direct.toFixed(2)} />
              <InspectorMetric label="Propagated" value={riskScore.propagated.toFixed(2)} />
            </>
          ) : null}
        </InspectorMetricGrid>

        {node.clusterId ? (
          <InspectorField label="Cluster">
            <InspectorMonoValue
              value={node.clusterId}
              className="text-[var(--aegis-text-secondary)]"
            />
          </InspectorField>
        ) : null}

        <InspectorField label="Asset ID">
          <InspectorMonoValue value={node.id} />
        </InspectorField>

        {showPath ? (
          <div
            className="flex flex-col gap-1 border-t border-[var(--aegis-border-subtle)] pt-3"
            data-testid="path-inspector-section"
          >
            <InspectorLabel>Highlighted path</InspectorLabel>
            <InspectorMonoBlock>{pathNodes.join(' → ')}</InspectorMonoBlock>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
