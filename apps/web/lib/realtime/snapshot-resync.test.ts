import { afterEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

import { buildBootstrapFromEndpoints } from './snapshot-resync';
import { ApiClientError } from '@/lib/api/types';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

const RUN_RECORD = {
  schemaVersion: 1,
  id: RUN_ID,
  scenarioVersionId: 'scenario-version:1.0.0',
  seed: 42,
  status: 'running',
  startedAt: '2026-01-01T00:00:00Z',
  simTime: '2026-01-01T00:01:00Z',
  revision: 3,
};

const GRAPH_SNAPSHOT = {
  schemaVersion: 1,
  runId: RUN_ID,
  sequence: 7,
  revision: 7,
  capturedAt: '2026-01-01T00:01:00Z',
  nodes: [],
  edges: [],
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

function requestedPaths(): string[] {
  return apiFetch.mock.calls.map((call) => String(call[0]));
}

afterEach(() => {
  apiFetch.mockReset();
});

describe('buildBootstrapFromEndpoints', () => {
  it('uses the composite endpoint alone when it answers', async () => {
    apiFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        schemaVersion: 1,
        run: RUN_RECORD,
        graphSnapshot: GRAPH_SNAPSHOT,
        lastAppliedSequence: 9,
      }),
    );

    const bootstrap = await buildBootstrapFromEndpoints(RUN_ID);

    expect(bootstrap.lastAppliedSequence).toBe(9);
    expect(requestedPaths()).toEqual([`/api/v1/runs/${RUN_ID}/bootstrap`]);
  });

  it('assembles from the per-resource endpoints when the composite one is absent', async () => {
    apiFetch
      .mockResolvedValueOnce(jsonResponse(404, { detail: 'not found' }))
      .mockResolvedValueOnce(jsonResponse(200, RUN_RECORD))
      .mockResolvedValueOnce(jsonResponse(200, GRAPH_SNAPSHOT));

    const bootstrap = await buildBootstrapFromEndpoints(RUN_ID);

    expect(bootstrap.run.id).toBe(RUN_ID);
    expect(bootstrap.lastAppliedSequence).toBe(GRAPH_SNAPSHOT.sequence);
    expect(requestedPaths()).toHaveLength(3);
  });

  it('does not fan a rate-limited bootstrap out into two more requests', async () => {
    // The defect this guards: one failing bootstrap used to become a `/runs/{id}` +
    // `/runs/{id}/graph` pair, so the client answered "slow down" by tripling its load. QA
    // captured 43 such pairs, all 429, from a single tab.
    apiFetch.mockResolvedValueOnce(jsonResponse(429, { code: 'RATE_LIMIT_EXCEEDED' }));

    await expect(buildBootstrapFromEndpoints(RUN_ID)).rejects.toBeInstanceOf(ApiClientError);

    expect(requestedPaths()).toEqual([`/api/v1/runs/${RUN_ID}/bootstrap`]);
  });

  it('does not fan a server error out either', async () => {
    apiFetch.mockResolvedValueOnce(jsonResponse(503, { code: 'UNAVAILABLE' }));

    await expect(buildBootstrapFromEndpoints(RUN_ID)).rejects.toBeInstanceOf(ApiClientError);

    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it('falls back when the composite payload fails this client’s schema', async () => {
    // A 200 the client cannot parse is a structural mismatch, not load: the narrower
    // per-resource schemas may still succeed, so trying them is worth the two requests.
    apiFetch
      .mockResolvedValueOnce(jsonResponse(200, { schemaVersion: 1, unexpected: true }))
      .mockResolvedValueOnce(jsonResponse(200, RUN_RECORD))
      .mockResolvedValueOnce(jsonResponse(200, GRAPH_SNAPSHOT));

    const bootstrap = await buildBootstrapFromEndpoints(RUN_ID);

    expect(bootstrap.run.id).toBe(RUN_ID);
    expect(apiFetch).toHaveBeenCalledTimes(3);
  });
});
