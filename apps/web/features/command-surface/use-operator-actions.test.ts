import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { readRunLoadout, useSubmitOperatorAction } from './use-operator-actions';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return createElement(QueryClientProvider, { client }, children);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('useSubmitOperatorAction', () => {
  it('posts the operator action with the confirm flag and target asset', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          schemaVersion: 1,
          proposalId: 'proposal:p1',
          incidentId: 'incident:i1',
          actionClass: 'class_2',
          status: 'executed',
          policyOutcome: 'approval_required',
          reasonCodes: [],
          executed: true,
        }),
    });

    const { result } = renderHook(() => useSubmitOperatorAction('run_x'), { wrapper });
    await result.current.mutateAsync({
      command: 'isolate',
      targetAssetId: 'asset:vpn-gw',
      reason: 'Contain lateral movement',
      confirm: true,
    });

    const [path, init] = apiFetch.mock.calls[0] as [string, RequestInit];
    expect(path).toBe('/api/v1/runs/run_x/operator-actions');
    expect(init.method).toBe('POST');
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body).toMatchObject({
      scenarioCommand: 'isolate',
      targetAssetId: 'asset:vpn-gw',
      reason: 'Contain lateral movement',
      confirm: true,
    });
    expect(typeof body.idempotencyKey).toBe('string');
  });

  it('surfaces a policy block as a resolved response, not a throw', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          schemaVersion: 1,
          proposalId: 'proposal:p2',
          incidentId: 'incident:i2',
          actionClass: 'class_3',
          status: 'blocked',
          policyOutcome: 'block',
          reasonCodes: ['blocked_criticality_threshold'],
          executed: false,
        }),
    });
    const { result } = renderHook(() => useSubmitOperatorAction('run_x'), { wrapper });
    const response = await result.current.mutateAsync({
      command: 'rollback_deployment',
      targetAssetId: 'asset:svc',
      reason: 'test',
      confirm: true,
    });
    expect(response.status).toBe('blocked');
    expect(response.reasonCodes).toContain('blocked_criticality_threshold');
  });

  it('reads the loadout defensively, treating legacy runs as having none', () => {
    expect(readRunLoadout(null)).toBeNull();
    expect(readRunLoadout({ id: 'run_x' })).toBeNull();
    expect(
      readRunLoadout({
        loadout: { schemaVersion: 1, biasGuard: false, threatTempo: true, roe: 'observe' },
      }),
    ).toMatchObject({ biasGuard: false, threatTempo: true, roe: 'observe' });
  });
});
