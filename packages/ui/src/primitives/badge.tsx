import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { StatusIcon } from '../semantic/icons';
import { getNodeStatusPresentation, getOperationalStatusPresentation } from '../semantic/status';
import type { NodeStatusValue } from '../tokens/status-tokens';

const badgeVariants = cva(
  'inline-flex min-h-6 items-center gap-1.5 rounded-full border border-transparent px-2.5 py-1 text-[0.6875rem] font-semibold leading-none tracking-[0.045em] shadow-[inset_0_1px_0_rgb(255_255_255_/_0.04)]',
  {
    variants: {
      variant: {
        default:
          'border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] text-[var(--aegis-text-primary)]',
        outline:
          'border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)]/60 text-[var(--aegis-text-secondary)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  nodeStatus?: NodeStatusValue;
  operationalStatus?: 'loading' | 'error' | 'disconnected' | 'empty';
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, nodeStatus, operationalStatus, children, ...props }, ref) => {
    const presentation = nodeStatus
      ? getNodeStatusPresentation(nodeStatus)
      : operationalStatus
        ? getOperationalStatusPresentation(operationalStatus)
        : null;

    return (
      <span
        ref={ref}
        className={cn(badgeVariants({ variant }), presentation?.tokenClass, className)}
        aria-label={presentation?.ariaLabel}
        {...props}
      >
        {presentation ? (
          <StatusIcon
            icon={presentation.icon}
            shape={presentation.shape}
            label={presentation.label}
            animate={presentation.icon === 'loader'}
          />
        ) : null}
        <span>{children ?? presentation?.label}</span>
      </span>
    );
  },
);
Badge.displayName = 'Badge';

export { badgeVariants };
