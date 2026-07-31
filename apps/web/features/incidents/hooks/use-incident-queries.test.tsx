import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AlertV1, IncidentV1, RunV1 } from '@aegis/contracts-ts';

import type { AegisApiClient } from '@/lib/api/types';
import { ApiClientError } from '@/lib/api/types';

const useApiClient = vi.fn();

vi.mock('@/lib/api/api-client-provider', () => ({
  useApiClient: () => useApiClient() as AegisApiClient,
}));

// Imported after the mock is registered.
import { useIncidentQueue } from './use-incident-queries';

function run(id: string): RunV1 {
  return {
    schemaVersion: 1,
    id,
    scenarioVersionId: 'scenario-version:v1.0.0-synthetic',
    seed: 1,
    status: 'running',
    startedAt: '2026-06-30T02:00:00.000Z',
    simTime: '2026-01-01T00:00:00.000Z',
    revision: 1,
  } as RunV1;
}

function incident(id: string, runId: string, alertIds: string[]): IncidentV1 {
  return {
    schemaVersion: 1,
    id,
    runId,
    title: `Incident ${id}`,
    state: 'open',
    alertIds,
    createdAt: '2026-06-30T02:01:00.000Z',
    updatedAt: '2026-06-30T02:01:00.000Z',
    revision: 0,
  } as IncidentV1;
}

function alert(id: string, runId: string, severity: string): AlertV1 {
  return { schemaVersion: 1, id, runId, severity, title: id } as AlertV1;
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/**
 * The queue used to read incidents *and* alerts for every run, so a 16-run workspace
 * issued 33 simultaneous requests and crossed the API's per-session burst limit. These
 * tests pin the shape that fixed it: incidents arrive in one cross-run request, and
 * alerts are read only where they can change a row.
 */
describe('useIncidentQueue', () => {
  function client(overrides: Partial<AegisApiClient> = {}) {
    // The spies are returned rather than read back off the client object, so assertions
    // never reference a method unbound from its receiver.
    const spies = {
      listRuns: vi.fn(async () => Promise.resolve([run('run_a'), run('run_b'), run('run_c')])),
      listAllIncidents: vi.fn(async () =>
        Promise.resolve([incident('incident:1', 'run_a', ['alert:run_a'])]),
      ),
      listIncidents: vi.fn(async () => Promise.resolve([])),
      listAlerts: vi.fn(async (runId: string) =>
        Promise.resolve([alert(`alert:${runId}`, runId, 'critical')]),
      ),
    };
    useApiClient.mockReturnValue({ ...spies, ...overrides } as unknown as AegisApiClient);
    return spies;
  }

  it('reads incidents once for every visible run instead of per run', async () => {
    const spies = client();
    const { result } = renderHook(() => useIncidentQueue(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(spies.listAllIncidents).toHaveBeenCalledTimes(1);
    expect(spies.listIncidents).not.toHaveBeenCalled();
  });

  it('reads alerts only for the runs that actually have an incident', async () => {
    const spies = client();
    const { result } = renderHook(() => useIncidentQueue(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    // Three visible runs, one with an incident: one alert request, not three.
    expect(spies.listAlerts).toHaveBeenCalledTimes(1);
    expect(spies.listAlerts).toHaveBeenCalledWith('run_a', expect.anything());
    expect(result.current.data?.[0]?.severity).toBe('critical');
  });

  it('keeps the queue up when a run’s alerts fail to load', async () => {
    client({
      listAlerts: vi.fn(async () =>
        Promise.reject(
          new ApiClientError({ code: 'RATE_LIMIT_EXCEEDED', message: 'slow down', status: 429 }),
        ),
      ),
    });
    const { result } = renderHook(() => useIncidentQueue(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    // The row survives; only its severity degrades, because alerts are the sole source
    // of severity and nothing else on the row depends on them.
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0]?.incident.id).toBe('incident:1');
    expect(result.current.data?.[0]?.severity).toBe('info');
  });

  it('fails the query when the incident list itself cannot be read', async () => {
    client({
      listAllIncidents: vi.fn(async () =>
        Promise.reject(
          new ApiClientError({ code: 'UNAUTHENTICATED', message: 'expired', status: 401 }),
        ),
      ),
    });
    const { result } = renderHook(() => useIncidentQueue(), { wrapper });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect((result.current.error as ApiClientError).status).toBe(401);
  });

  it('drops incidents whose run is not visible rather than rendering a runless row', async () => {
    client({
      listAllIncidents: vi.fn(async () =>
        Promise.resolve([
          incident('incident:1', 'run_a', []),
          incident('incident:ghost', 'run_deleted', []),
        ]),
      ),
    });
    const { result } = renderHook(() => useIncidentQueue(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.map((row) => row.incident.id)).toEqual(['incident:1']);
  });
});
