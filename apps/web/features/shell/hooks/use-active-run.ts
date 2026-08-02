'use client';

import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { useOptionalAuth } from '@/features/auth';
import { useApiClient } from '@/lib/api/api-client-provider';
import { queryKeys } from '@/lib/api/query-keys';
import { isNotFoundError } from '@/lib/api/types';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

/**
 * One answer to "which run is the operator on", shared by every navigation surface.
 *
 * The rail and the command palette used to each decide this for themselves, and the rail's
 * answer was the route alone — so the moment the operator opened Incidents or Reports the
 * rail's "Active run" resolved to nothing and silently linked to the catalogue instead of
 * the run they had just left.
 */

const RUN_SCOPED_ROUTE = /^\/(?:runs|replay|after-action)\/([^/?#]+)/;

/** The run id a run-scoped route names, or `null` off such a route. */
export function activeRunIdFromPath(pathname: string | null): string | null {
  if (!pathname) {
    return null;
  }
  const captured = RUN_SCOPED_ROUTE.exec(pathname)?.[1];
  return captured ? decodeURIComponent(captured) : null;
}

/**
 * Resolve the operator's run: the route first, then the run they were last on.
 *
 * Also maintains the remembered value — entering a run surface records it, a remembered run
 * belonging to a different identity is dropped rather than followed (it is persisted across
 * sign-ins and following it lands on a 403 workspace), and a remembered run the server no
 * longer has is evicted.
 *
 * That last rule is not housekeeping. The context outlives the run: QA deleted a tutorial run
 * and every surface that reads this hook went on naming it for the rest of the session, each
 * quietly polling its own endpoint into a 404 forever. A run that 404s is gone, and the only
 * correct response is to stop claiming the operator is on it.
 */
export function useActiveRunId(): string | null {
  const pathname = usePathname();
  const auth = useOptionalAuth();
  const client = useApiClient();
  const userId = auth?.actor?.userId ?? null;
  const runContext = useWorkspaceUiStore((state) => state.runContext);
  const rememberRunContext = useWorkspaceUiStore((state) => state.rememberRunContext);
  const clearRunContext = useWorkspaceUiStore((state) => state.clearRunContext);

  // Run ids this hook has already watched 404. State rather than a ref because the answer
  // this hook returns depends on it: learning that a run is gone has to re-render the caller
  // that is still linking to it, and clearing the remembered context only does that for the
  // one candidate that came from the store.
  const [missingRunIds, setMissingRunIds] = useState<ReadonlySet<string>>(() => new Set());
  const markRunMissing = useCallback((runId: string) => {
    setMissingRunIds((current) => (current.has(runId) ? current : new Set(current).add(runId)));
  }, []);

  const runIdFromPath = activeRunIdFromPath(pathname);
  const rememberedRunId =
    runContext !== null && userId !== null && runContext.userId === userId
      ? runContext.runId
      : null;

  const candidateRunId = runIdFromPath ?? rememberedRunId;
  const candidateIsMissing = candidateRunId !== null && missingRunIds.has(candidateRunId);

  // Shares its key with every other reader of the run record, so on a run surface this is
  // already cached and costs nothing; off one it is a single request that replaces the
  // repeated 404s a dead context used to generate. 404 is non-retryable under the shared
  // retry policy, so a missing run is asked about exactly once.
  const runQuery = useQuery({
    queryKey: queryKeys.runs.detail(candidateRunId ?? ''),
    queryFn: ({ signal }) => client.getRun(candidateRunId ?? '', signal),
    enabled: candidateRunId !== null && !candidateIsMissing,
  });

  const runQueryError = runQuery.error;
  useEffect(() => {
    if (candidateRunId === null || !isNotFoundError(runQueryError)) {
      return;
    }
    markRunMissing(candidateRunId);
    if (runContext?.runId === candidateRunId) {
      clearRunContext();
    }
  }, [candidateRunId, clearRunContext, markRunMissing, runContext, runQueryError]);

  useEffect(() => {
    if (runIdFromPath !== null && userId !== null && !missingRunIds.has(runIdFromPath)) {
      rememberRunContext({ runId: runIdFromPath, userId });
      return;
    }
    // Stale identity: whoever is signed in now did not create this context. Session still
    // loading (`userId === null`) is not that — leave it alone until identity resolves.
    if (runContext !== null && userId !== null && runContext.userId !== userId) {
      clearRunContext();
    }
  }, [runIdFromPath, userId, runContext, rememberRunContext, clearRunContext, missingRunIds]);

  // The route may still name a run that no longer exists; the route's own guard renders the
  // not-found surface. What this hook must not do is hand that id to the rail and the palette
  // as somewhere the operator can go back to.
  return candidateIsMissing ? null : candidateRunId;
}
