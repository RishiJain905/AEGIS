'use client';

import { useEffect } from 'react';

import type { AssetRiskScoreV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import { Badge, Panel } from '@aegis/ui';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';
import {
  isPendingControlFresh,
  usePendingControlStore,
} from '@/features/operator-actions/pending-control-store';

import {
  InspectorField,
  InspectorLabel,
  InspectorMetric,
  InspectorMetricGrid,
  InspectorMonoBlock,
  InspectorMonoValue,
} from './inspector-primitives';

/**
 * Operator-facing names for the applied-control vocabulary.
 *
 * The world stores the response toolkit's own terms; the inspector is where an operator
 * reads what was done to the asset, and "observed" is a state the machine is in, not a
 * sentence about the estate. Unknown values fall back to the raw term rather than being
 * hidden — a control we have no copy for still has to be visible.
 */
const CONTROL_LABEL: Record<string, string> = {
  observed: 'Under observation',
  heightened_monitoring: 'Heightened monitoring',
  isolated: 'Isolated',
  access_restricted: 'Access restricted',
  credentials_revoked: 'Credentials revoked',
  restarting: 'Restarting',
  rolling_back: 'Rolling back',
  contained: 'Contained',
  quarantined: 'Quarantined',
};

function controlLabel(control: string): string {
  return CONTROL_LABEL[control] ?? control.replace(/_/g, ' ');
}

export interface GraphEntityInspectorProps {
  snapshot: GraphSnapshotV1;
  selectedEntityId: string | null;
  riskScore?: AssetRiskScoreV1 | null;
  /**
   * A risk total from a source that carries no direct/propagated split — the replay
   * projection, which reconstructs one score per asset and nothing about how it was
   * reached. Supplying it shows the total and omits the breakdown; the alternative is
   * to synthesize `direct = total, propagated = 0`, which reads as a real decomposition
   * and is wrong for every asset whose risk actually arrived from a neighbour.
   */
  riskTotal?: number | null;
}

export function GraphEntityInspector({
  snapshot,
  selectedEntityId,
  riskScore,
  riskTotal,
}: GraphEntityInspectorProps) {
  const visualState = useGraphVisualStore((s) => s.visualState);
  const pendingControls = usePendingControlStore((s) => s.pending);
  const clearPendingControl = usePendingControlStore((s) => s.clear);

  const node = selectedEntityId
    ? (snapshot.nodes.find((n) => n.id === selectedEntityId) ?? null)
    : null;
  const appliedControls = node?.appliedControls ?? [];
  const pending = node ? pendingControls[node.id] : undefined;
  // The acknowledgment exists only to cover the gap before the control lands. Once the
  // node carries one — or the order has been unanswered long enough to stop meaning
  // anything — drop it rather than keep promising something that never arrived.
  const pendingResolved =
    pending !== undefined && (appliedControls.length > 0 || !isPendingControlFresh(pending));

  useEffect(() => {
    if (node && pendingResolved) {
      clearPendingControl(node.id);
    }
  }, [node, pendingResolved, clearPendingControl]);

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
          {/*
            Posture and applied controls are two different facts and the inspector shows
            both: the status badge is what is wrong with the asset, the control badges are
            what we have done about it. Reading only the first would put a compromised
            host under observation and make it look merely "under investigation".
          */}
          <div className="flex flex-wrap gap-2">
            <Badge>{node.assetType}</Badge>
            <Badge variant="outline">{node.status.replace(/_/g, ' ')}</Badge>
            {appliedControls.map((control) => (
              <Badge key={control} variant="outline" data-testid="applied-control-badge">
                {controlLabel(control)}
              </Badge>
            ))}
            {pending && !pendingResolved ? (
              <Badge
                variant="outline"
                data-testid="pending-control-badge"
                className="border-dashed border-[var(--aegis-accent-line)] text-[var(--aegis-accent-strong)]"
              >
                {pending.label} · applying
              </Badge>
            ) : null}
          </div>
        </div>

        <InspectorMetricGrid>
          <InspectorMetric
            label="Risk score"
            value={(riskScore?.total ?? riskTotal ?? node.riskScore).toFixed(2)}
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
