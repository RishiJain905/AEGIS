import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { StatusIcon } from '../semantic/icons';
import { getOperationalStatusPresentation } from '../semantic/status';
import { Skeleton } from '../primitives/skeleton';

export interface LoadingStateProps extends HTMLAttributes<HTMLDivElement> {
  message?: string;
}

export const LoadingState = forwardRef<HTMLDivElement, LoadingStateProps>(
  ({ className, message = 'Loading data…', ...props }, ref) => {
    const presentation = getOperationalStatusPresentation('loading');
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        aria-label={presentation.ariaLabel}
        className={cn('flex flex-col items-center gap-3 p-6 text-center', className)}
        {...props}
      >
        <StatusIcon
          icon={presentation.icon}
          shape={presentation.shape}
          label={presentation.label}
          animate
        />
        <p className="text-sm text-[var(--aegis-text-secondary)]">{message}</p>
        <Skeleton className="h-2 w-48" />
      </div>
    );
  },
);
LoadingState.displayName = 'LoadingState';

export interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
}

export const EmptyState = forwardRef<HTMLDivElement, EmptyStateProps>(
  (
    { className, title = 'No data', description = 'There is nothing to display yet.', ...props },
    ref,
  ) => {
    const presentation = getOperationalStatusPresentation('empty');
    return (
      <div
        ref={ref}
        role="status"
        aria-label={presentation.ariaLabel}
        className={cn('flex flex-col items-center gap-3 p-6 text-center', className)}
        {...props}
      >
        <StatusIcon
          icon={presentation.icon}
          shape={presentation.shape}
          label={presentation.label}
        />
        <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">{title}</h3>
        <p className="text-sm text-[var(--aegis-text-secondary)]">{description}</p>
      </div>
    );
  },
);
EmptyState.displayName = 'EmptyState';

export interface ErrorStateProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export const ErrorState = forwardRef<HTMLDivElement, ErrorStateProps>(
  (
    {
      className,
      title = 'Something went wrong',
      message = 'An error occurred while loading.',
      onRetry,
      ...props
    },
    ref,
  ) => {
    const presentation = getOperationalStatusPresentation('error');
    return (
      <div
        ref={ref}
        role="alert"
        aria-label={presentation.ariaLabel}
        className={cn('flex flex-col items-center gap-3 p-6 text-center', className)}
        {...props}
      >
        <StatusIcon
          icon={presentation.icon}
          shape={presentation.shape}
          label={presentation.label}
        />
        <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">{title}</h3>
        <p className="text-sm text-[var(--aegis-text-secondary)]">{message}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-default)] px-3 py-1.5 text-sm text-[var(--aegis-text-primary)] hover:bg-[var(--aegis-surface-elevated)]"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  },
);
ErrorState.displayName = 'ErrorState';

export interface DisconnectedStateProps extends HTMLAttributes<HTMLDivElement> {
  message?: string;
}

export const DisconnectedState = forwardRef<HTMLDivElement, DisconnectedStateProps>(
  (
    { className, message = 'Realtime connection lost. Attempting to reconnect…', ...props },
    ref,
  ) => {
    const presentation = getOperationalStatusPresentation('disconnected');
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        aria-label={presentation.ariaLabel}
        className={cn(
          'flex items-center gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-status-disconnected)] bg-[var(--aegis-status-disconnected-bg)] px-4 py-3',
          className,
        )}
        {...props}
      >
        <StatusIcon
          icon={presentation.icon}
          shape={presentation.shape}
          label={presentation.label}
        />
        <span className="text-sm text-[var(--aegis-text-primary)]">{message}</span>
      </div>
    );
  },
);
DisconnectedState.displayName = 'DisconnectedState';
