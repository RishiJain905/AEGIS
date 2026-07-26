'use client';

import { notFound } from 'next/navigation';
import { type ReactNode, useEffect, useRef, useState } from 'react';

import { Button, ErrorState, LoadingState } from '@aegis/ui';

import { useIncident, useRun } from '@/features/shell/hooks/use-shell-queries';
import { isNotFoundError } from '@/lib/api';

interface ShellRouteGuardProps {
  runId?: string;
  incidentId?: string;
  children: ReactNode;
}

/**
 * Non-destructive error affordance. Once the cockpit is mounted its live
 * WebSocket and reducer state must survive a failed refetch, so a transient
 * error is surfaced beside the children instead of replacing them.
 */
function ShellRouteErrorBanner({
  onRetry,
  onDismiss,
}: {
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <div
      role="alert"
      data-testid="shell-route-error"
      className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4"
    >
      <div className="pointer-events-auto flex max-w-xl items-center gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-status-error)] bg-[var(--aegis-surface-overlay)] px-4 py-3 shadow-lg">
        <span className="text-sm text-[var(--aegis-text-primary)]">
          Unable to refresh workspace data. Showing the last known state.
        </span>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}

export function ShellRouteGuard({ runId, incidentId, children }: ShellRouteGuardProps) {
  const runQuery = useRun(runId ?? '');
  const incidentQuery = useIncident(incidentId ?? '');

  const activeQuery = incidentId ? incidentQuery : runId ? runQuery : null;
  const routeKey = incidentId ?? runId ?? '';

  const isNotFound = Boolean(activeQuery?.isError && isNotFoundError(activeQuery.error));
  const isTransientError = Boolean(activeQuery?.isError) && !isNotFound;

  // Tracks the route whose children have already mounted. Anything mounted must
  // stay mounted: unmounting the shell tears down LiveRunProvider, which kills
  // the WebSocket and triggers a full bootstrap on the next render — the
  // feedback loop that made every transient error self-amplifying.
  const mountedRouteRef = useRef<string | null>(null);
  const hasMountedChildren = mountedRouteRef.current === routeKey;

  const [dismissedErrorAt, setDismissedErrorAt] = useState<number | null>(null);

  useEffect(() => {
    if (isNotFound) {
      notFound();
    }
  }, [isNotFound]);

  // `data` survives a failed refetch, so its presence means the workspace was
  // loaded at least once for this route.
  const canRenderChildren = !activeQuery || activeQuery.data !== undefined || hasMountedChildren;

  useEffect(() => {
    if (canRenderChildren) {
      mountedRouteRef.current = routeKey;
    }
  }, [canRenderChildren, routeKey]);

  if (!activeQuery) {
    return <>{children}</>;
  }

  if (!canRenderChildren) {
    if (isTransientError) {
      // Nothing has mounted yet, so there is no live connection to protect.
      return (
        <ErrorState
          data-testid="shell-route-error"
          message="Unable to load workspace data."
          onRetry={() => void activeQuery.refetch()}
        />
      );
    }
    return <LoadingState message="Loading workspace…" data-testid="shell-route-loading" />;
  }

  const errorUpdatedAt = isTransientError ? activeQuery.errorUpdatedAt : null;
  const showErrorBanner = errorUpdatedAt !== null && errorUpdatedAt !== dismissedErrorAt;

  return (
    <>
      {children}
      {showErrorBanner ? (
        <ShellRouteErrorBanner
          onRetry={() => void activeQuery.refetch()}
          onDismiss={() => {
            setDismissedErrorAt(errorUpdatedAt);
          }}
        />
      ) : null}
    </>
  );
}
