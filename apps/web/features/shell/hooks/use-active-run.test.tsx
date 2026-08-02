import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiClientError } from '@/lib/api/types';

let pathname: string | null = '/incidents';
vi.mock('next/navigation', () => ({
  usePathname: () => pathname,
}));

vi.mock('@/features/auth', () => ({
  useOptionalAuth: () => ({ actor: { userId: 'user:admin-alpha' } }),
}));

const getRun =
  vi.fn<(runId: string, signal?: AbortSignal) => Promise<{ id: string; status: string }>>();
vi.mock('@/lib/api/api-client-provider', () => ({
  useApiClient: () => ({ getRun: (runId: string, signal?: AbortSignal) => getRun(runId, signal) }),
}));

import { useActiveRunId } from './use-active-run';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const LIVE_RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const DELETED_RUN = 'run_E02AHM3GRDCYE9CDMM1PBTD3D1';

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function notFound(): ApiClientError {
  return new ApiClientError({ code: 'NOT_FOUND', message: 'Run not found', status: 404 });
}

beforeEach(() => {
  pathname = '/incidents';
  useWorkspaceUiStore.getState().clearRunContext();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('useActiveRunId', () => {
  it('follows the run the operator was last on when off a run route', () => {
    getRun.mockResolvedValue({ id: LIVE_RUN, status: 'running' });
    act(() => {
      useWorkspaceUiStore
        .getState()
        .rememberRunContext({ runId: LIVE_RUN, userId: 'user:admin-alpha' });
    });

    const { result } = renderHook(() => useActiveRunId(), { wrapper });

    expect(result.current).toBe(LIVE_RUN);
  });

  it('evicts a remembered run the server no longer has', async () => {
    // QA deleted a tutorial run and every surface reading this hook kept naming it for the
    // rest of the session, each polling its own endpoint into a 404 forever.
    getRun.mockRejectedValue(notFound());
    act(() => {
      useWorkspaceUiStore
        .getState()
        .rememberRunContext({ runId: DELETED_RUN, userId: 'user:admin-alpha' });
    });

    const { result } = renderHook(() => useActiveRunId(), { wrapper });

    await waitFor(() => {
      expect(result.current).toBeNull();
    });
    expect(useWorkspaceUiStore.getState().runContext).toBeNull();
  });

  it('asks about a missing run once rather than on every render', async () => {
    getRun.mockRejectedValue(notFound());
    act(() => {
      useWorkspaceUiStore
        .getState()
        .rememberRunContext({ runId: DELETED_RUN, userId: 'user:admin-alpha' });
    });

    const { result, rerender } = renderHook(() => useActiveRunId(), { wrapper });
    await waitFor(() => {
      expect(result.current).toBeNull();
    });

    rerender();
    rerender();

    expect(getRun).toHaveBeenCalledTimes(1);
  });

  it('does not re-remember a run that was just evicted', async () => {
    // The route still names the dead run (the operator arrived by URL). Remembering it again
    // after eviction would ping-pong with the clear on every render.
    pathname = `/runs/${DELETED_RUN}`;
    getRun.mockRejectedValue(notFound());

    const { result } = renderHook(() => useActiveRunId(), { wrapper });

    await waitFor(() => {
      expect(result.current).toBeNull();
    });
    expect(useWorkspaceUiStore.getState().runContext).toBeNull();
  });
});
