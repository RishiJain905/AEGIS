import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useRun, useIncident, notFound } = vi.hoisted(() => ({
  useRun: vi.fn(),
  useIncident: vi.fn(),
  notFound: vi.fn(),
}));

vi.mock('next/navigation', () => ({ notFound }));
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRun,
  useIncident,
}));

import { ShellRouteGuard } from '@/features/shell/components/shell-route-guard';
import { ApiClientError } from '@/lib/api';

interface QueryStub {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  data: unknown;
  errorUpdatedAt: number;
  refetch: () => void;
}

function queryStub(overrides: Partial<QueryStub> = {}): QueryStub {
  return {
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
    errorUpdatedAt: 0,
    refetch: vi.fn(),
    ...overrides,
  };
}

const idleQuery = queryStub({ isPending: true });
const loadedRun = { runId: 'run_1' };

let mountCount = 0;

/** Stands in for the cockpit shell: its remount count is what we assert on. */
function Cockpit() {
  useEffect(() => {
    mountCount += 1;
  }, []);
  return <div data-testid="cockpit">cockpit</div>;
}

function renderGuard() {
  return render(
    <ShellRouteGuard runId="run_1">
      <Cockpit />
    </ShellRouteGuard>,
  );
}

function rateLimited(errorUpdatedAt: number, data: unknown): QueryStub {
  return queryStub({
    isError: true,
    error: new ApiClientError({
      code: 'RATE_LIMITED',
      message: 'Too many requests',
      status: 429,
    }),
    errorUpdatedAt,
    data,
  });
}

describe('ShellRouteGuard', () => {
  beforeEach(() => {
    mountCount = 0;
    useRun.mockReturnValue(idleQuery);
    useIncident.mockReturnValue(idleQuery);
    notFound.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('shows the loading state before anything has mounted', () => {
    renderGuard();
    expect(screen.getByTestId('shell-route-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('cockpit')).not.toBeInTheDocument();
  });

  it('shows a full error state when the first load fails', () => {
    useRun.mockReturnValue(rateLimited(1, undefined));
    renderGuard();
    expect(screen.getByTestId('shell-route-error')).toBeInTheDocument();
    expect(screen.queryByTestId('cockpit')).not.toBeInTheDocument();
  });

  it('keeps the mounted shell alive when a later request fails', () => {
    useRun.mockReturnValue(queryStub({ data: loadedRun }));
    const { rerender } = renderGuard();
    expect(screen.getByTestId('cockpit')).toBeInTheDocument();
    expect(mountCount).toBe(1);

    // A transient failure arrives; the shell (and its WebSocket) must survive.
    useRun.mockReturnValue(rateLimited(1_000, loadedRun));
    rerender(
      <ShellRouteGuard runId="run_1">
        <Cockpit />
      </ShellRouteGuard>,
    );

    expect(screen.getByTestId('cockpit')).toBeInTheDocument();
    expect(screen.getByTestId('shell-route-error')).toBeInTheDocument();
    expect(mountCount).toBe(1);

    // Even after the cache drops the stale data the shell stays mounted.
    useRun.mockReturnValue(rateLimited(2_000, undefined));
    rerender(
      <ShellRouteGuard runId="run_1">
        <Cockpit />
      </ShellRouteGuard>,
    );

    expect(screen.getByTestId('cockpit')).toBeInTheDocument();
    expect(mountCount).toBe(1);
  });

  it('dismisses the inline error without disturbing the shell, and resurfaces a new one', () => {
    useRun.mockReturnValue(queryStub({ data: loadedRun }));
    const { rerender } = renderGuard();

    useRun.mockReturnValue(rateLimited(1_000, loadedRun));
    rerender(
      <ShellRouteGuard runId="run_1">
        <Cockpit />
      </ShellRouteGuard>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));

    expect(screen.queryByTestId('shell-route-error')).not.toBeInTheDocument();
    expect(screen.getByTestId('cockpit')).toBeInTheDocument();

    // A fresh failure is a new error instance and must be shown again.
    useRun.mockReturnValue(rateLimited(2_000, loadedRun));
    rerender(
      <ShellRouteGuard runId="run_1">
        <Cockpit />
      </ShellRouteGuard>,
    );

    expect(screen.getByTestId('shell-route-error')).toBeInTheDocument();
    expect(mountCount).toBe(1);
  });

  it('retries the query from the inline error affordance', () => {
    const refetch = vi.fn();
    useRun.mockReturnValue(queryStub({ data: loadedRun }));
    const { rerender } = renderGuard();

    useRun.mockReturnValue({ ...rateLimited(1_000, loadedRun), refetch });
    rerender(
      <ShellRouteGuard runId="run_1">
        <Cockpit />
      </ShellRouteGuard>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it('still triggers notFound() for a genuine 404', () => {
    useRun.mockReturnValue(
      queryStub({
        isError: true,
        error: new ApiClientError({
          code: 'NOT_FOUND',
          message: 'missing',
          status: 404,
        }),
        errorUpdatedAt: 1,
      }),
    );
    renderGuard();
    expect(notFound).toHaveBeenCalled();
  });
});
