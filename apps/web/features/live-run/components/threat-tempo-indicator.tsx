'use client';

import { useThreatTempo } from '@/features/live-run/hooks/use-threat-tempo';

export interface ThreatTempoBand {
  /** Qualitative level surfaced to assistive tech and shown as the readout label. */
  label: string;
  /** Foreground/fill colour token, escalating from quiet to critical. */
  color: string;
  /** Whether the fill should pulse (only ever animated when motion is allowed). */
  pulse: boolean;
}

/**
 * Map a tempo scalar to a qualitative pressure band. Exported for tests and to keep the
 * thresholds in one place. The scalar itself never names an asset or condition — this is
 * ambient tension only.
 */
export function threatTempoBand(tempo: number): ThreatTempoBand {
  if (tempo >= 0.85) {
    return { label: 'critical', color: 'var(--aegis-risk-critical)', pulse: true };
  }
  if (tempo >= 0.65) {
    return { label: 'high', color: 'var(--aegis-risk-high)', pulse: true };
  }
  if (tempo >= 0.4) {
    return { label: 'elevated', color: 'var(--aegis-risk-medium)', pulse: false };
  }
  if (tempo >= 0.15) {
    return { label: 'low', color: 'var(--aegis-risk-low)', pulse: false };
  }
  return { label: 'quiet', color: 'var(--aegis-text-muted)', pulse: false };
}

interface ThreatTempoIndicatorProps {
  runId: string;
}

/**
 * Ambient fog-of-war pressure indicator for the run status area.
 *
 * Subtle by design: a thin pressure meter that fills and warms as undetected attacker
 * progress accrues, evoking "something is escalating" without ever revealing what. Hidden
 * entirely when the run carries no fog tension (null tempo) or the loadout opts out. Motion
 * is confined to `motion-safe`, so a reduced-motion operator still sees the level change and
 * the qualitative readout, just without the pulse.
 */
export function ThreatTempoIndicator({ runId }: ThreatTempoIndicatorProps) {
  const { data } = useThreatTempo(runId);

  if (data === undefined || data.tempo === null || !data.loadoutEnabled) {
    return null;
  }

  const tempo = Math.max(0, Math.min(1, data.tempo));
  const band = threatTempoBand(tempo);
  const percent = Math.round(tempo * 100);

  return (
    <div
      className="flex items-center gap-2 border-l border-[var(--aegis-border-subtle)] pl-4"
      data-testid="threat-tempo"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-label={`Threat tempo: ${band.label}`}
      title={`Threat tempo: ${band.label} (${String(percent)}%)`}
    >
      <span className="font-[family-name:var(--aegis-font-display)] text-[0.6875rem] font-semibold uppercase tracking-[0.13em] text-[var(--aegis-text-muted)]">
        Threat tempo
      </span>
      <span
        className="relative h-1.5 w-20 overflow-hidden rounded-full bg-[var(--aegis-border-subtle)]"
        aria-hidden="true"
      >
        <span
          className={`absolute inset-y-0 left-0 rounded-full transition-[width,background-color] duration-700 ease-out ${
            band.pulse ? 'motion-safe:animate-pulse' : ''
          }`}
          style={{
            width: `${String(percent)}%`,
            backgroundColor: band.color,
            boxShadow: band.pulse ? `0 0 8px 0 ${band.color}` : undefined,
          }}
        />
      </span>
      <span
        className="font-[family-name:var(--aegis-font-mono)] text-[0.625rem] uppercase tracking-[0.08em] tabular-nums"
        style={{ color: band.color }}
      >
        {band.label}
      </span>
    </div>
  );
}
