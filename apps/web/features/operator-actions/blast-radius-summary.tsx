'use client';

import { Badge } from '@aegis/ui';

import type { BlastRadiusImpactV1, BlastRadiusPreviewV1 } from '@aegis/contracts-ts';

export interface BlastRadiusSummaryProps {
  preview: BlastRadiusPreviewV1 | undefined;
  loading: boolean;
  error: boolean;
}

const IMPACT_TONE: Record<BlastRadiusImpactV1['impactKind'], string> = {
  severed: 'var(--aegis-risk-critical)',
  outage: 'var(--aegis-risk-high)',
  degraded: 'var(--aegis-risk-medium)',
};

const IMPACT_LABEL: Record<BlastRadiusImpactV1['impactKind'], string> = {
  severed: 'severed',
  outage: 'outage',
  degraded: 'degraded',
};

function AssetChip({ impact }: { impact: BlastRadiusImpactV1 }) {
  const tone = IMPACT_TONE[impact.impactKind];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-[var(--aegis-radius-sm)] border px-1.5 py-0.5"
      style={{ borderColor: tone }}
      title={`${impact.relationshipType} · ${IMPACT_LABEL[impact.impactKind]}`}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: tone }}
      />
      <span className="text-[11px] text-[var(--aegis-text-primary)]">{impact.label}</span>
      <span className="font-mono text-[9px] text-[var(--aegis-text-muted)]">
        {Math.round(impact.criticality * 100)}%
      </span>
    </span>
  );
}

/**
 * Projected collateral of a Class 2/3 containment, above the confirm/approve control. The
 * projection is decision support only — on load failure the dialog still works, so we degrade
 * to a quiet note rather than blocking the operator.
 */
export function BlastRadiusSummary({ preview, loading, error }: BlastRadiusSummaryProps) {
  return (
    <section
      aria-label="Projected impact"
      data-testid="blast-radius-summary"
      className="flex flex-col gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-3 py-2"
    >
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
          Projected impact
        </p>
        {preview ? (
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className="text-[9px]" data-testid="blast-radius-severed">
              {preview.severedEdgeCount} severed
            </Badge>
            <Badge variant="outline" className="text-[9px]" data-testid="blast-radius-degraded">
              {preview.degradedEdgeCount} degraded
            </Badge>
          </div>
        ) : null}
      </div>

      {loading ? (
        <p className="text-xs text-[var(--aegis-text-muted)]" data-testid="blast-radius-loading">
          Projecting collateral over the current graph…
        </p>
      ) : null}

      {error && !loading ? (
        <p className="text-xs text-[var(--aegis-text-muted)]" data-testid="blast-radius-error">
          Impact preview unavailable — proceed with standard caution.
        </p>
      ) : null}

      {preview && !loading ? (
        <div className="flex flex-col gap-2">
          {preview.impactedAssets.length > 0 ? (
            <div
              className="flex flex-wrap items-center gap-1.5"
              data-testid="blast-radius-impacted"
            >
              {preview.impactedAssets.map((impact) => (
                <AssetChip key={impact.edgeId} impact={impact} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--aegis-text-secondary)]">
              No neighbouring assets are severed or degraded by this action.
            </p>
          )}

          {preview.downstreamAssets.length > 0 ? (
            <p
              className="text-[11px] text-[var(--aegis-text-secondary)]"
              data-testid="blast-radius-downstream"
            >
              Cascades to {preview.downstreamAssets.length} downstream service
              {preview.downstreamAssets.length === 1 ? '' : 's'}:{' '}
              {preview.downstreamAssets
                .slice(0, 4)
                .map((d) => d.label)
                .join(', ')}
              {preview.downstreamAssets.length > 4 ? '…' : ''}
            </p>
          ) : null}

          {preview.warnings.length > 0 ? (
            <ul className="flex flex-col gap-0.5" data-testid="blast-radius-warnings">
              {preview.warnings.map((warning) => (
                <li key={warning} className="text-[11px] text-[var(--aegis-text-secondary)]">
                  • {warning}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
