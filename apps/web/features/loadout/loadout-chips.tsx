'use client';

import { VisuallyHidden } from '@aegis/ui';

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

function IntentChip({ intent }: { intent: string }) {
  const preview = intent.length > 40 ? `${intent.slice(0, 40).trimEnd()}…` : intent;
  return (
    <span
      tabIndex={0}
      title={intent}
      data-testid="loadout-intent-chip"
      className="inline-flex max-w-[16rem] items-center gap-1 rounded-full border border-[var(--aegis-accent-line)] bg-[color-mix(in_srgb,var(--aegis-accent-soft)_60%,transparent)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-accent-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--aegis-accent-line)]"
    >
      <VisuallyHidden>Commander&apos;s intent: {intent}</VisuallyHidden>
      <span aria-hidden="true">Intent</span>
      <span
        aria-hidden="true"
        className="truncate normal-case tracking-normal text-[var(--aegis-text-secondary)]"
      >
        {preview}
      </span>
    </span>
  );
}

/**
 * Compact loadout summary for the run header: which capabilities were armed at launch, the
 * current rules of engagement, and (when set) a commander's-intent chip that reveals the full
 * intent on hover/focus. Reflects the run's persisted loadout/intent; renders nothing when the
 * run has neither (legacy runs use the default and simply omit the chips).
 */
export function LoadoutChips({
  loadout,
  commanderIntent,
}: {
  loadout: RunLoadout | null;
  commanderIntent?: string | null;
}) {
  const intent = commanderIntent?.trim() ?? '';
  if (!loadout && intent.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Run loadout">
      {loadout && <Chip label="Bias guard" active={loadout.biasGuard} />}
      {loadout && <Chip label="Threat tempo" active={loadout.threatTempo} />}
      {loadout && (
        <span className="inline-flex items-center gap-1 rounded-full border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-accent-strong)]">
          RoE · {ROE_DOCTRINE[loadout.roe].label}
        </span>
      )}
      {intent.length > 0 && <IntentChip intent={intent} />}
    </div>
  );
}
