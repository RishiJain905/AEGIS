import type { GraphNodeV1 } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { buildClusterPresentationNodes, toggleCollapsedCluster } from './cluster-presentation';

const nodes: GraphNodeV1[] = [
  {
    schemaVersion: 1,
    id: 'asset:a',
    entityType: 'asset',
    assetType: 'service',
    label: 'A',
    clusterId: 'business-unit:cluster-01',
    riskScore: 0.1,
    criticality: 0.1,
    status: 'normal',
    revision: 1,
  },
  {
    schemaVersion: 1,
    id: 'asset:b',
    entityType: 'asset',
    assetType: 'service',
    label: 'B',
    clusterId: 'business-unit:cluster-01',
    riskScore: 0.1,
    criticality: 0.1,
    status: 'normal',
    revision: 1,
  },
];

describe('cluster presentation', () => {
  it('collapses and expands cluster presentation nodes', () => {
    const collapsed = buildClusterPresentationNodes(
      nodes,
      [
        {
          schemaVersion: 1,
          id: 'business-unit:cluster-01',
          label: 'Cluster 01',
          memberNodeIds: ['asset:a', 'asset:b'],
          revision: 1,
        },
      ],
      ['business-unit:cluster-01'],
    );

    expect(collapsed.presentationNodes).toHaveLength(1);
    expect(collapsed.hiddenNodeIds.size).toBe(2);
    expect(
      toggleCollapsedCluster(['business-unit:cluster-01'], 'business-unit:cluster-01'),
    ).toEqual([]);
  });
});
