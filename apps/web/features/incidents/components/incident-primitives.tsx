'use client';

import { Badge, cn, getRiskBandPresentation, type RiskBand } from '@aegis/ui';

import {
  getIncidentStatePresentation,
  severityToRiskBand,
  type SeverityLevel,
} from '../lib/incident-model';
import type { IncidentV1 } from '@aegis/contracts-ts';

/**
 * Solid severity fills keyed to the reserved risk palette — for the thin triage
 * accents (queue row rails, pending markers) where a bright hairline of colour
 * carries the signal without the chip's tinted background.
 */
export const SEVERITY_ACCENT_BG: Record<RiskBand, string> = {
  low: 'bg-[var(--aegis-risk-low)]',
  medium: 'bg-[var(--aegis-risk-medium)]',
  high: 'bg-[var(--aegis-risk-high)]',
  critical: 'bg-[var(--aegis-risk-critical)]',
};

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
        'inline-flex min-h-6 items-center justify-center rounded-full px-2.5 py-1 text-[0.625rem] font-semibold uppercase leading-none tracking-[0.09em] ring-1 ring-inset ring-[color-mix(in_srgb,currentColor_22%,transparent)]',
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
    <div className="flex flex-col gap-1">
      <span className="text-[0.625rem] font-semibold uppercase leading-none tracking-[0.12em] text-[var(--aegis-text-faint)]">
        {label}
      </span>
      <span className="text-sm leading-5 text-[var(--aegis-text-secondary)]">{children}</span>
    </div>
  );
}
