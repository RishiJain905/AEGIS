import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  animate?: boolean;
}

export const Skeleton = forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, animate = true, ...props }, ref) => (
    <div
      ref={ref}
      aria-hidden="true"
      className={cn(
        'rounded-[var(--aegis-radius-sm)] bg-[linear-gradient(90deg,var(--aegis-surface-overlay),var(--aegis-surface-raised),var(--aegis-surface-overlay))]',
        animate && 'aegis-motion-pulse',
        className,
      )}
      {...props}
    />
  ),
);
Skeleton.displayName = 'Skeleton';
