import { describe, expect, it } from 'vitest';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import {
  computeInitialLayout,
  filterNodesBySearch,
} from '@/features/operational-graph/layout/initial-layout';

function makeNode(id: string, clusterId?: string): GraphNodeV1 {
  return {
    schemaVersion: 1,
    id,
    entityType: 'asset',
    assetType: 'service',
    label: id,
    clusterId,
    riskScore: 0.5,
    criticality: 0.5,
    status: 'normal',
    revision: 1,
  };
}

describe('initial layout', () => {
  it('produces deterministic positions sorted by node id', () => {
    const nodes = [makeNode('asset:b', 'c1'), makeNode('asset:a', 'c1')];
    const first = computeInitialLayout(nodes, []);
    const second = computeInitialLayout(nodes, []);
    expect(first).toEqual(second);
    expect(first['asset:a']).toBeDefined();
    expect(first['asset:b']).toBeDefined();
  });

  it('preserves existing positions', () => {
    const nodes = [makeNode('asset:a')];
    const existing = { 'asset:a': { x: 10, y: 20 } };
    const result = computeInitialLayout(nodes, [], existing);
    expect(result['asset:a']).toEqual({ x: 10, y: 20 });
  });
});

describe('filterNodesBySearch', () => {
  it('filters by label and id', () => {
    const labels = new Map([
      ['asset:svc-api-gateway', 'API Gateway'],
      ['asset:svc-auth-service', 'Auth Service'],
    ]);
    const result = filterNodesBySearch(
      ['asset:svc-api-gateway', 'asset:svc-auth-service'],
      labels,
      'gateway',
    );
    expect(result).toEqual(['asset:svc-api-gateway']);
  });

  it('returns all nodes when query is empty', () => {
    const labels = new Map([['asset:a', 'Alpha']]);
    expect(filterNodesBySearch(['asset:a'], labels, '')).toEqual(['asset:a']);
  });
});
