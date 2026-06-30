import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';
import { GRAPH_PATH_RESULT_SCHEMA_VERSION } from '@aegis/contracts-ts';

import { buildConnectedSnapshot } from './helpers';

describe('path queries', () => {
  it('returns deterministic lexicographic path ordering', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const result = store.queryPaths({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sourceId: 'asset:device-c',
      targetId: 'asset:svc-b',
      maxHops: 4,
      relationshipTypes: [],
      directedOnly: true,
    });

    expect(result.schemaVersion).toBe(GRAPH_PATH_RESULT_SCHEMA_VERSION);
    expect(result.paths).toEqual([['asset:device-c', 'asset:svc-a', 'asset:svc-b']]);
    expect(result.explanation.ordering).toBe('lexicographic_by_node_id');
  });

  it('filters by relationship type', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const result = store.queryPaths({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sourceId: 'asset:device-c',
      targetId: 'asset:svc-b',
      maxHops: 4,
      relationshipTypes: ['COMMUNICATED_WITH'],
      directedOnly: true,
    });

    expect(result.paths).toHaveLength(0);
    expect(result.explanation.pathsFound).toBe(0);
  });

  it('returns empty paths when endpoints are missing', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const result = store.queryPaths({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sourceId: 'asset:missing',
      targetId: 'asset:svc-b',
      maxHops: 2,
      relationshipTypes: [],
      directedOnly: true,
    });

    expect(result.paths).toEqual([]);
    expect(result.explanation.reason).toBe('source_or_target_not_found');
  });
});
