import type { ReactNode } from 'react';

import { cn, typographyTokens } from '@aegis/ui';

/**
 * Quiet section heading for the admin surfaces: a Chakra Petch eyebrow, an
 * optional count, and a hairline rule that carries the label across the panel.
 * Establishes a shared vertical rhythm instead of a stack of equal-weight
 * `font-semibold` headings.
 */
export function SectionHeading({
  children,
  count,
  className,
}: {
  children: ReactNode;
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <h3 className="font-[family-name:var(--aegis-font-display)] text-[0.7rem] font-semibold uppercase tracking-[0.1em] text-[var(--aegis-text-secondary)]">
        {children}
      </h3>
      {typeof count === 'number' ? (
        <span
          className={cn(
            typographyTokens.monoSm,
            'rounded-full bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 leading-none text-[var(--aegis-text-muted)]',
          )}
        >
          {count}
        </span>
      ) : null}
      <span aria-hidden="true" className="h-px flex-1 bg-[var(--aegis-border-subtle)]" />
    </div>
  );
}
