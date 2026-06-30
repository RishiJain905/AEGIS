import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { densityTokens, type DensityToken } from '../tokens/tokens';

const panelVariants = cva(
  'flex flex-col rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)]',
  {
    variants: {
      density: {
        compact: densityTokens.compact,
        comfortable: densityTokens.comfortable,
        spacious: densityTokens.spacious,
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

export interface PanelProps
  extends HTMLAttributes<HTMLElement>,
    VariantProps<typeof panelVariants> {
  title?: string;
  description?: string;
}

export const Panel = forwardRef<HTMLElement, PanelProps>(
  ({ className, density, responsive, title, description, children, ...props }, ref) => (
    <section
      ref={ref}
      className={cn(panelVariants({ density, responsive }), className)}
      aria-label={title}
      {...props}
    >
      {(title ?? description) ? (
        <header className="border-b border-[var(--aegis-border-subtle)] pb-3">
          {title ? (
            <h2 className="text-base font-semibold text-[var(--aegis-text-primary)]">{title}</h2>
          ) : null}
          {description ? (
            <p className="text-sm text-[var(--aegis-text-secondary)]">{description}</p>
          ) : null}
        </header>
      ) : null}
      <div className="flex-1">{children}</div>
    </section>
  ),
);
Panel.displayName = 'Panel';

export type { DensityToken };
