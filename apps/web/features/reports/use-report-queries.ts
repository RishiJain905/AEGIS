'use client';

import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api';
import { useApiClient } from '@/lib/api/api-client-provider';

const REPORT_ELIGIBLE_RUN_STATUSES = new Set(['completed', 'stopped']);

/** The after-action report (and its version history) only exist once a run
 * has reached a terminal state — SCRIBE generates it after completion.
 * Fetching either endpoint before that is a guaranteed 404 on every page
 * load; gate the queries on this instead of eating the error each time. */
export function isReportEligibleRunStatus(status: string | undefined): boolean {
  return status !== undefined && REPORT_ELIGIBLE_RUN_STATUSES.has(status);
}

/** Run status for gating the report queries below. Uses the same query key
 * as `useRun` (features/shell/hooks/use-shell-queries) so it shares that
 * cache entry rather than firing a second request — deliberately not
 * importing that hook directly, since shell already renders ReportsPanel/
 * ReportsWorkspace and importing back would create a circular dependency
 * between features/shell and features/reports. */
export function useRunStatusForReports(runId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.detail(runId),
    queryFn: ({ signal }) => client.getRun(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useAfterActionReport(runId: string, options?: { enabled?: boolean }) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.afterActionReport(runId),
    queryFn: ({ signal }) => client.getAfterActionReport(runId, signal),
    enabled: Boolean(runId) && (options?.enabled ?? true),
    // A terminal run whose SCRIBE pass has not run yet answers 404, and that is an answer,
    // not a flake: retrying turns one honest "not ready" into four console errors.
    retry: false,
  });
}

export function useReportVersions(runId: string, options?: { enabled?: boolean }) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs.reportVersions(runId),
    queryFn: ({ signal }) => client.listAfterActionReportVersions(runId, signal),
    enabled: Boolean(runId) && (options?.enabled ?? true),
    retry: false,
  });
}
