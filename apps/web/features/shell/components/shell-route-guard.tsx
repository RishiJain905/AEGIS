'use client';

import { notFound } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';

import { ErrorState, LoadingState } from '@aegis/ui';

import { useIncident, useRun } from '@/features/shell/hooks/use-shell-queries';
import { isNotFoundError } from '@/lib/api';

interface ShellRouteGuardProps {
  runId?: string;
  incidentId?: string;
  children: ReactNode;
}

export function ShellRouteGuard({ runId, incidentId, children }: ShellRouteGuardProps) {
  const runQuery = useRun(runId ?? '');
  const incidentQuery = useIncident(incidentId ?? '');

  const activeQuery = incidentId ? incidentQuery : runId ? runQuery : null;

  useEffect(() => {
    if (!activeQuery?.isError) {
      return;
    }
    if (isNotFoundError(activeQuery.error)) {
      notFound();
    }
  }, [activeQuery?.isError, activeQuery?.error]);

  if (!activeQuery) {
    return <>{children}</>;
  }

  if (activeQuery.isPending) {
    return <LoadingState message="Loading workspace…" data-testid="shell-route-loading" />;
  }

  if (activeQuery.isError && !isNotFoundError(activeQuery.error)) {
    return (
      <ErrorState
        data-testid="shell-route-error"
        message="Unable to load workspace data."
        onRetry={() => void activeQuery.refetch()}
      />
    );
  }

  return <>{children}</>;
}
