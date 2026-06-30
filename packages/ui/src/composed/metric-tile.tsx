import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { RiskIcon } from '../semantic/icons';
import { getRiskBandPresentation, type RiskBand } from '../semantic/risk';
import { Badge } from '../primitives/badge';
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
          'flex flex-col gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] p-4',
          className,
        )}
        aria-label={`${label}: ${String(value)}`}
        {...props}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-[var(--aegis-text-secondary)]">
            {label}
          </span>
          {risk ? <RiskIcon band={risk.band} /> : null}
          {nodeStatus ? <Badge nodeStatus={nodeStatus} /> : null}
        </div>
        <div className="text-2xl font-semibold text-[var(--aegis-text-primary)]">{value}</div>
        {trend ? <div className="text-xs text-[var(--aegis-text-muted)]">{trend}</div> : null}
      </div>
    );
  },
);
MetricTile.displayName = 'MetricTile';
