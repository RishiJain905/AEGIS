import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';

import { buildConnectedSnapshot } from './helpers';

describe('neighborhoods and incident subgraph', () => {
  it('returns k-hop rings deterministically sorted', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const result = store.getNeighborhood('asset:device-c', { hops: 2 });
    expect(result.nodeIds).toEqual(['asset:device-c', 'asset:svc-a', 'asset:svc-b']);
    expect(result.hopRings[0]).toEqual(['asset:svc-a']);
    expect(result.hopRings[1]).toEqual(['asset:svc-b']);
  });

  it('builds incident subgraph from seeds', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const result = store.getIncidentSubgraph(['asset:device-c'], { hops: 2 });
    expect(result.nodeIds).toContain('asset:svc-b');
    expect(result.edgeIds.length).toBeGreaterThan(0);
  });

  it('returns connected components', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    expect(store.getConnectedComponents()).toEqual([
      ['asset:device-c', 'asset:svc-a', 'asset:svc-b'],
    ]);
  });

  it('traverses DEPENDS_ON dependencies', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    expect(store.getDependencies('asset:svc-a')).toEqual(['asset:svc-b']);
  });

  it('returns cluster members from metadata', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    expect(store.getClusterMembers('business-unit:bu-platform')).toEqual([
      'asset:device-c',
      'asset:svc-a',
      'asset:svc-b',
    ]);
  });
});
