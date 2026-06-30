import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';

const railVariants = cva(
  'flex flex-col border-r border-[var(--aegis-border-default)] bg-[var(--aegis-surface-rail)] shadow-[var(--aegis-shadow-rail)]',
  {
    variants: {
      collapsed: {
        true: 'w-14',
        false: 'w-64',
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
      <div className={cn('flex flex-col gap-2 p-3', collapsed && 'items-center')}>{children}</div>
    </nav>
  ),
);
Rail.displayName = 'Rail';
