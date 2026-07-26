import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AuthSessionResponseV1 } from '@aegis/contracts-ts';

const { apiFetchJson, setMemoryCsrfToken } = vi.hoisted(() => ({
  apiFetchJson: vi.fn(),
  setMemoryCsrfToken: vi.fn(),
}));

vi.mock('@/lib/api/auth-fetch', () => ({ apiFetchJson, setMemoryCsrfToken }));

import { AuthProvider, useAuth } from '@/features/auth/auth-provider';
import { ApiClientError } from '@/lib/api';

const SESSION: AuthSessionResponseV1 = {
  schemaVersion: 1,
  authenticated: true,
  actor: {
    schemaVersion: 1,
    userId: 'user:alpha',
    displayName: 'Admin Alpha',
    roles: ['admin'],
    permissions: ['runs:read'],
    sessionId: 'sess_alpha_0001',
    authMethod: 'dev',
  },
  session: null,
};

function Probe() {
  const auth = useAuth();
  return <div data-testid="status">{auth.sessionStatus}</div>;
}

function renderProvider() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

function apiError(status: number): ApiClientError {
  return new ApiClientError({ code: 'HTTP_ERROR', message: 'failed', status });
}

describe('AuthProvider session query', () => {
  beforeEach(() => {
    apiFetchJson.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('retries a rate-limited session request instead of reporting a signed-out state', async () => {
    apiFetchJson.mockRejectedValueOnce(apiError(429)).mockResolvedValueOnce(SESSION);
    renderProvider();

    await waitFor(
      () => {
        expect(screen.getByTestId('status')).toHaveTextContent('authenticated');
      },
      { timeout: 4_000 },
    );
    expect(apiFetchJson).toHaveBeenCalledTimes(2);
  });

  it('retries a server error', async () => {
    apiFetchJson.mockRejectedValueOnce(apiError(503)).mockResolvedValueOnce(SESSION);
    renderProvider();

    await waitFor(
      () => {
        expect(screen.getByTestId('status')).toHaveTextContent('authenticated');
      },
      { timeout: 4_000 },
    );
    expect(apiFetchJson).toHaveBeenCalledTimes(2);
  });

  it('never retries a genuine 401 and reports the operator as signed out', async () => {
    apiFetchJson.mockRejectedValue(apiError(401));
    renderProvider();

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });
    expect(apiFetchJson).toHaveBeenCalledTimes(1);
  });

  it('reports an unauthenticated session response as signed out', async () => {
    apiFetchJson.mockResolvedValue({
      schemaVersion: 1,
      authenticated: false,
      actor: null,
    });
    renderProvider();

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });
  });
});
