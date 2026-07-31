'use client';

import { usePathname } from 'next/navigation';
import { useEffect } from 'react';

import { useOptionalAuth } from '@/features/auth';
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
 * Also maintains the remembered value — entering a run surface records it, and a
 * remembered run belonging to a different identity is dropped rather than followed, since
 * it is persisted across sign-ins and following it lands on a 403 workspace.
 */
export function useActiveRunId(): string | null {
  const pathname = usePathname();
  const auth = useOptionalAuth();
  const userId = auth?.actor?.userId ?? null;
  const runContext = useWorkspaceUiStore((state) => state.runContext);
  const rememberRunContext = useWorkspaceUiStore((state) => state.rememberRunContext);
  const clearRunContext = useWorkspaceUiStore((state) => state.clearRunContext);

  const runIdFromPath = activeRunIdFromPath(pathname);
  const rememberedRunId =
    runContext !== null && userId !== null && runContext.userId === userId
      ? runContext.runId
      : null;

  useEffect(() => {
    if (runIdFromPath !== null && userId !== null) {
      rememberRunContext({ runId: runIdFromPath, userId });
      return;
    }
    // Stale identity: whoever is signed in now did not create this context. Session still
    // loading (`userId === null`) is not that — leave it alone until identity resolves.
    if (runContext !== null && userId !== null && runContext.userId !== userId) {
      clearRunContext();
    }
  }, [runIdFromPath, userId, runContext, rememberRunContext, clearRunContext]);

  return runIdFromPath ?? rememberedRunId;
}
