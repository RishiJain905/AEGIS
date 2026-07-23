'use client';

import { ROE_DOCTRINE, type RunLoadout } from '@/features/command-surface/contracts';

function Chip({ label, active }: { label: string; active: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide"
      data-testid="loadout-chip"
    >
      <span
        aria-hidden="true"
        className="size-1.5 rounded-full"
        style={{
          backgroundColor: active ? 'var(--aegis-accent-cyan)' : 'var(--aegis-text-faint)',
        }}
      />
      <span
        className={active ? 'text-[var(--aegis-text-secondary)]' : 'text-[var(--aegis-text-muted)]'}
      >
        {label}
      </span>
    </span>
  );
}

/**
 * Compact loadout summary for the run header: which capabilities were armed at launch and the
 * current rules of engagement. Reflects the run's persisted loadout; renders nothing when the
 * run has no loadout (legacy runs use the default and simply omit the chips).
 */
export function LoadoutChips({ loadout }: { loadout: RunLoadout | null }) {
  if (!loadout) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Run loadout">
      <Chip label="Bias guard" active={loadout.biasGuard} />
      <Chip label="Threat tempo" active={loadout.threatTempo} />
      <span className="inline-flex items-center gap-1 rounded-full border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-accent-strong)]">
        RoE · {ROE_DOCTRINE[loadout.roe].label}
      </span>
    </div>
  );
}
