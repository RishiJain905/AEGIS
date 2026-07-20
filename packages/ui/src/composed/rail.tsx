import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';

const railVariants = cva(
  'flex flex-col overflow-y-auto rounded-[var(--aegis-radius-xl)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_80%,transparent)] shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl transition-[width] duration-[var(--aegis-motion-duration-normal)]',
  {
    variants: {
      collapsed: {
        true: 'w-[4.5rem]',
        false: 'w-60',
      },
      responsive: {
        true: 'hidden lg:flex',
        false: 'flex',
      },
    },
    defaultVariants: {
      collapsed: false,
      responsive: true,
    },
  },
);

export interface RailProps extends HTMLAttributes<HTMLElement>, VariantProps<typeof railVariants> {
  label?: string;
}

export const Rail = forwardRef<HTMLElement, RailProps>(
  ({ className, collapsed, responsive, label = 'Operations rail', children, ...props }, ref) => (
    <nav
      ref={ref}
      aria-label={label}
      className={cn(railVariants({ collapsed, responsive }), className)}
      {...props}
    >
      <div className={cn('flex flex-col gap-1.5 p-3', collapsed && 'items-center')}>{children}</div>
    </nav>
  ),
);
Rail.displayName = 'Rail';
