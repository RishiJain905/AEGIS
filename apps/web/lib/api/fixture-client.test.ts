import { describe, expect, it } from 'vitest';

import {
  createFixtureProvider,
  loadShellDataset,
  resetShellDatasetCache,
} from '@/lib/api/fixture-client';

describe('fixture client', () => {
  it('loads and validates the shell dataset', () => {
    resetShellDatasetCache();
    const dataset = loadShellDataset();
    expect(dataset.scenarios).toHaveLength(1);
    expect(dataset.runs[0]?.id).toBe('run_01ARZ3NDEKTSV4RRFFQ69G5FAV');
  });

  it('returns validated scenarios from the fixture provider', async () => {
    const client = createFixtureProvider({ profileId: 'default' });
    const scenarios = await client.listScenarios();
    expect(scenarios[0]?.id).toBe('scenario:scenario-synthetic-01');
  });

  it('simulates empty scenarios for the empty profile', async () => {
    const client = createFixtureProvider({ profileId: 'empty' });
    const scenarios = await client.listScenarios();
    expect(scenarios).toEqual([]);
  });

  it('throws ApiClientError for simulated error profile', async () => {
    const client = createFixtureProvider({ profileId: 'error' });
    await expect(client.listScenarios()).rejects.toMatchObject({
      name: 'ApiClientError',
      status: 500,
    });
  });

  it('returns partial graph for partial profile', async () => {
    const client = createFixtureProvider({ profileId: 'partial' });
    const graph = await client.getRunGraph('run_01ARZ3NDEKTSV4RRFFQ69G5FAV');
    expect(graph.partial).toBe(true);
    expect(graph.snapshot).toBeNull();
  });

  it('reports connection status from profile', async () => {
    const offline = createFixtureProvider({ profileId: 'offline' });
    await expect(offline.getConnectionStatus()).resolves.toBe('offline');

    const reconnecting = createFixtureProvider({ profileId: 'reconnecting' });
    await expect(reconnecting.getConnectionStatus()).resolves.toBe('reconnecting');
  });

  it('throws not found for unknown run', async () => {
    const client = createFixtureProvider();
    await expect(client.getRun('run_missing')).rejects.toMatchObject({ status: 404 });
  });
});
