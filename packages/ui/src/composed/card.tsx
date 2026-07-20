import { type ReactNode, forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  footer?: ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, title, description, footer, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)] p-4 shadow-[var(--aegis-shadow-panel)] before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[var(--aegis-border-highlight)]',
        className,
      )}
      {...props}
    >
      {(title ?? description) ? (
        <div className="mb-3">
          {title ? (
            <h3 className="font-[family-name:var(--aegis-font-display)] text-sm font-semibold tracking-[0.025em] text-[var(--aegis-text-primary)]">
              {title}
            </h3>
          ) : null}
          {description ? (
            <p className="mt-1 text-xs leading-5 text-[var(--aegis-text-secondary)]">
              {description}
            </p>
          ) : null}
        </div>
      ) : null}
      <div>{children}</div>
      {footer ? (
        <div className="mt-3 border-t border-[var(--aegis-border-subtle)] pt-3">{footer}</div>
      ) : null}
    </div>
  ),
);
Card.displayName = 'Card';
