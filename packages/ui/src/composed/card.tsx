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
        'rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] p-4 shadow-[var(--aegis-shadow-panel)]',
        className,
      )}
      {...props}
    >
      {(title ?? description) ? (
        <div className="mb-3">
          {title ? (
            <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">{title}</h3>
          ) : null}
          {description ? (
            <p className="text-xs text-[var(--aegis-text-secondary)]">{description}</p>
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
