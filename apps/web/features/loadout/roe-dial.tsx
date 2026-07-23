'use client';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
  cn,
} from '@aegis/ui';

import {
  ROE_DOCTRINE,
  RULES_OF_ENGAGEMENT,
  useChangeRoe,
  type RulesOfEngagement,
} from '@/features/command-surface';

const ROE_TONE: Record<RulesOfEngagement, string> = {
  observe: 'var(--aegis-text-muted)',
  investigate: 'var(--aegis-accent-cyan)',
  forward_deployed: 'var(--aegis-risk-medium)',
};

export interface RoeDialProps {
  runId: string;
  current: RulesOfEngagement;
  disabled?: boolean;
}

/**
 * Mid-run rules-of-engagement dial. Changing it PATCHes /runs/{id}/roe (audited via a
 * run.roe_changed event) and reflects the run's current autonomy doctrine. Kept compact for
 * the command status strip; the doctrine one-liner is shown in the menu so the operator sees
 * exactly what each level licenses the agents to do.
 */
export function RoeDial({ runId, current, disabled }: RoeDialProps) {
  const changeRoe = useChangeRoe(runId);
  const doctrine = ROE_DOCTRINE[current];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled || changeRoe.isPending}
          data-testid="roe-dial"
          className="flex items-center gap-1.5 rounded-full border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] px-2.5 py-1 text-[0.6875rem] transition-colors hover:border-[var(--aegis-border-strong)] disabled:opacity-60"
          aria-label={`Rules of engagement: ${doctrine.label}. Change.`}
        >
          <span
            aria-hidden="true"
            className="size-1.5 rounded-full"
            style={{ backgroundColor: ROE_TONE[current] }}
          />
          <span className="font-mono uppercase tracking-wide text-[var(--aegis-text-muted)]">
            RoE
          </span>
          <span className="font-medium text-[var(--aegis-text-secondary)]">{doctrine.label}</span>
          {changeRoe.isPending ? (
            <span className="text-[var(--aegis-text-muted)]">…</span>
          ) : (
            <span aria-hidden="true" className="text-[var(--aegis-text-muted)]">
              ▾
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[16rem]">
        <DropdownMenuLabel>Rules of engagement</DropdownMenuLabel>
        {RULES_OF_ENGAGEMENT.map((candidate) => {
          const meta = ROE_DOCTRINE[candidate];
          const selected = candidate === current;
          return (
            <DropdownMenuItem
              key={candidate}
              onSelect={() => {
                if (!selected) {
                  changeRoe.mutate(candidate);
                }
              }}
              data-testid={`roe-set-${candidate}`}
              className={cn(selected && 'bg-[var(--aegis-accent-soft)]')}
            >
              <div className="flex flex-col gap-0.5">
                <span className="flex items-center gap-1.5 text-sm text-[var(--aegis-text-primary)]">
                  <span
                    aria-hidden="true"
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: ROE_TONE[candidate] }}
                  />
                  {meta.label}
                  {selected ? (
                    <span className="text-[10px] text-[var(--aegis-text-muted)]">· current</span>
                  ) : null}
                </span>
                <span className="text-[10px] leading-4 text-[var(--aegis-text-muted)]">
                  {meta.doctrine}
                </span>
              </div>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
