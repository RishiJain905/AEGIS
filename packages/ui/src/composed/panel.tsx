import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { typographyTokens, type DensityToken } from '../tokens/tokens';

const panelVariants = cva(
  'relative flex flex-col overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)] before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[var(--aegis-border-highlight)]',
  {
    variants: {
      density: {
        compact: '',
        comfortable: '',
        spacious: '',
      },
      responsive: {
        true: 'w-full lg:max-w-none md:max-w-full',
        false: '',
      },
    },
    defaultVariants: {
      density: 'comfortable',
      responsive: true,
    },
  },
);

const panelDensityClasses: Record<DensityToken, { header: string; body: string }> = {
  compact: { header: 'px-4 py-3', body: 'p-4' },
  comfortable: { header: 'px-5 py-4', body: 'p-5' },
  spacious: { header: 'px-6 py-5', body: 'p-6' },
};

export interface PanelProps
  extends HTMLAttributes<HTMLElement>,
    VariantProps<typeof panelVariants> {
  title?: string;
  description?: string;
}

export const Panel = forwardRef<HTMLElement, PanelProps>(
  (
    { className, density = 'comfortable', responsive, title, description, children, ...props },
    ref,
  ) => {
    const resolvedDensity = density ?? 'comfortable';

    return (
      <section
        ref={ref}
        className={cn(panelVariants({ density: resolvedDensity, responsive }), className)}
        aria-label={title}
        {...props}
      >
        {(title ?? description) ? (
          <header
            data-slot="panel-header"
            className={cn(
              'border-b border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)]',
              panelDensityClasses[resolvedDensity].header,
            )}
          >
            {title ? (
              <h2 className={cn(typographyTokens.displayMd, 'text-[var(--aegis-text-primary)]')}>
                {title}
              </h2>
            ) : null}
            {description ? (
              <p className="mt-1 max-w-3xl text-sm leading-5 text-[var(--aegis-text-secondary)]">
                {description}
              </p>
            ) : null}
          </header>
        ) : null}
        <div
          data-slot="panel-body"
          className={cn('min-h-0 flex-1', panelDensityClasses[resolvedDensity].body)}
        >
          {children}
        </div>
      </section>
    );
  },
);
Panel.displayName = 'Panel';

export type { DensityToken };
