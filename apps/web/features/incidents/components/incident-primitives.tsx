'use client';

import { Badge, cn, getRiskBandPresentation } from '@aegis/ui';

import {
  getIncidentStatePresentation,
  severityToRiskBand,
  type SeverityLevel,
} from '../lib/incident-model';
import type { IncidentV1 } from '@aegis/contracts-ts';

export function SeverityChip({
  severity,
  className,
}: {
  severity: SeverityLevel;
  className?: string;
}) {
  const risk = getRiskBandPresentation(severityToRiskBand(severity));
  return (
    <span
      className={cn(
        'inline-flex min-h-6 items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.6875rem] font-semibold uppercase leading-none tracking-[0.05em]',
        risk.tokenClass,
        className,
      )}
      aria-label={`Severity: ${severity}`}
    >
      {severity}
    </span>
  );
}

export function IncidentStateBadge({
  state,
  className,
}: {
  state: IncidentV1['state'];
  className?: string;
}) {
  const presentation = getIncidentStatePresentation(state);
  return (
    <Badge nodeStatus={presentation.nodeStatus} className={className}>
      {presentation.label}
    </Badge>
  );
}

/** Small labelled fact, used across the incident header and side rail. */
export function MetaItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[0.625rem] font-semibold uppercase tracking-[0.1em] text-[var(--aegis-text-muted)]">
        {label}
      </span>
      <span className="text-sm text-[var(--aegis-text-secondary)]">{children}</span>
    </div>
  );
}
