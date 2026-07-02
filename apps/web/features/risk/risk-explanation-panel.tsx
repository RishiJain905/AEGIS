'use client';

import type { AssetRiskScoreV1 } from '@aegis/contracts-ts';
import { Badge, Panel } from '@aegis/ui';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';

export interface RiskExplanationPanelProps {
  riskScore: AssetRiskScoreV1 | null;
  directDetectionScore?: number | null;
}

export function RiskExplanationPanel({
  riskScore,
  directDetectionScore,
}: RiskExplanationPanelProps) {
  const setHighlight = useGraphVisualStore((state) => state.setHighlight);

  if (!riskScore) {
    return null;
  }

  const topContribution = riskScore.topContributions[0];

  return (
    <Panel title="Graph risk" density="compact" data-testid="risk-explanation-panel">
      <dl className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Total</dt>
          <dd className="font-mono">{riskScore.total.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Direct</dt>
          <dd className="font-mono" data-testid="risk-direct-score">
            {riskScore.direct.toFixed(2)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--aegis-text-muted)]">Propagated</dt>
          <dd className="font-mono" data-testid="risk-propagated-score">
            {riskScore.propagated.toFixed(2)}
          </dd>
        </div>
      </dl>

      {directDetectionScore != null ? (
        <div className="mt-2 flex items-center gap-2 text-xs" data-testid="risk-comparison">
          <Badge>Detection {directDetectionScore.toFixed(2)}</Badge>
          <span className="text-[var(--aegis-text-muted)]">vs graph {riskScore.total.toFixed(2)}</span>
        </div>
      ) : null}

      {topContribution ? (
        <div className="mt-3 border-t border-[var(--aegis-border-subtle)] pt-3">
          <p className="text-xs font-semibold text-[var(--aegis-text-muted)]">Explanation path</p>
          <p className="mt-1 font-mono text-xs">
            {topContribution.explanationPath.nodeIds.join(' → ')}
          </p>
          <p className="mt-2 text-xs text-[var(--aegis-text-muted)]">
            Source signal {topContribution.signalId} · hops {topContribution.hopCount} · contribution{' '}
            {topContribution.amount.toFixed(2)}
          </p>
          <button
            type="button"
            className="mt-2 text-xs text-[var(--aegis-accent)] underline"
            data-testid="highlight-risk-path"
            onClick={() => {
              setHighlight('path', topContribution.explanationPath.nodeIds, [], false);
            }}
          >
            Highlight path on graph
          </button>
        </div>
      ) : null}

      <p className="mt-2 text-[10px] text-[var(--aegis-text-muted)]">
        Deterministic graph-risk-v1 propagation (not GNN)
      </p>
    </Panel>
  );
}
