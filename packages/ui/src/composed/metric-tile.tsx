import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { RiskIcon } from '../semantic/icons';
import { getRiskBandPresentation, type RiskBand } from '../semantic/risk';
import { Badge } from '../primitives/badge';
import { typographyTokens } from '../tokens/tokens';
import type { NodeStatusValue } from '../tokens/status-tokens';

export interface MetricTileProps extends HTMLAttributes<HTMLDivElement> {
  label: string;
  value: string | number;
  trend?: string;
  riskBand?: RiskBand;
  nodeStatus?: NodeStatusValue;
}

export const MetricTile = forwardRef<HTMLDivElement, MetricTileProps>(
  ({ className, label, value, trend, riskBand, nodeStatus, ...props }, ref) => {
    const risk = riskBand ? getRiskBandPresentation(riskBand) : null;

    return (
      <div
        ref={ref}
        className={cn(
          'relative flex min-h-32 flex-col justify-between gap-3 overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] p-4 shadow-[var(--aegis-shadow-panel)] before:pointer-events-none before:absolute before:inset-y-3 before:left-0 before:w-0.5 before:rounded-r before:bg-[var(--aegis-accent-line)]',
          className,
        )}
        aria-label={`${label}: ${String(value)}`}
        {...props}
      >
        <div className="flex items-center justify-between gap-2">
          <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-secondary)]')}>
            {label}
          </span>
          {risk ? <RiskIcon band={risk.band} /> : null}
          {nodeStatus ? <Badge nodeStatus={nodeStatus} /> : null}
        </div>
        <div
          className={cn(
            typographyTokens.displayXl,
            'text-[var(--aegis-text-primary)] tabular-nums',
          )}
        >
          {value}
        </div>
        {trend ? (
          <div className="text-xs leading-5 text-[var(--aegis-text-muted)]">{trend}</div>
        ) : null}
      </div>
    );
  },
);
MetricTile.displayName = 'MetricTile';
