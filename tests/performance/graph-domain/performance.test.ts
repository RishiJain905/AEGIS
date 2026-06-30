import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';

import { loadMediumSnapshot } from '../../unit/graph-domain/helpers';

describe('graph-domain performance baselines', () => {
  it('loads a medium snapshot within budget', () => {
    const store = createGraphStore();
    const snapshot = loadMediumSnapshot();
    const start = performance.now();
    store.loadSnapshot(snapshot);
    const elapsed = performance.now() - start;
    expect(store.exportSnapshot().nodes.length).toBe(2500);
    expect(elapsed).toBeLessThan(5000);
  });

  it('applies a batch of deltas within budget', () => {
    const store = createGraphStore();
    const snapshot = loadMediumSnapshot();
    store.loadSnapshot(snapshot);

    const deltas = Array.from({ length: 100 }, (_, index) => ({
      schemaVersion: 1 as const,
      runId: snapshot.runId,
      sequence: snapshot.sequence + index + 1,
      revision: snapshot.revision + index + 1,
      operation: 'upsert_node' as const,
      node: {
        ...snapshot.nodes[index]!,
        riskScore: 0.99,
        revision: snapshot.nodes[index]!.revision + 1,
      },
    }));

    const start = performance.now();
    const results = store.applyDeltas(deltas);
    const elapsed = performance.now() - start;

    expect(results.every((result) => result.status === 'applied')).toBe(true);
    expect(elapsed).toBeLessThan(5000);
  });

  it('runs path and neighborhood queries within budget', () => {
    const store = createGraphStore();
    store.loadSnapshot(loadMediumSnapshot());

    const pathStart = performance.now();
    const pathResult = store.queryPaths({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sourceId: 'asset:node-00000',
      targetId: 'asset:node-02499',
      maxHops: 6,
      relationshipTypes: [],
      directedOnly: true,
    });
    const pathElapsed = performance.now() - pathStart;

    const neighborhoodStart = performance.now();
    const neighborhood = store.getNeighborhood('asset:node-00100', { hops: 2 });
    const neighborhoodElapsed = performance.now() - neighborhoodStart;

    expect(pathResult.paths.length).toBeGreaterThanOrEqual(0);
    expect(neighborhood.nodeIds.length).toBeGreaterThan(1);
    expect(pathElapsed).toBeLessThan(3000);
    expect(neighborhoodElapsed).toBeLessThan(1000);
  });

  it('clears store without retaining graph order', () => {
    const store = createGraphStore();
    store.loadSnapshot(loadMediumSnapshot());
    store.clear();
    expect(store.getRunId()).toBeNull();
    expect(() => store.exportSnapshot()).toThrow();
  });
});
