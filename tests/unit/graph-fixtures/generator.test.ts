import { describe, expect, it } from 'vitest';

import {
  buildStressGraphSnapshot,
  buildTargetGraphSnapshot,
  TARGET_GRAPH_NODE_COUNT,
} from '@aegis/graph-domain';

describe('graph fixture generator', () => {
  it('builds deterministic target and stress snapshots', () => {
    const targetA = buildTargetGraphSnapshot();
    const targetB = buildTargetGraphSnapshot();
    const stress = buildStressGraphSnapshot();

    expect(targetA.nodes.length).toBe(TARGET_GRAPH_NODE_COUNT);
    expect(targetA).toEqual(targetB);
    expect(stress.nodes.length).toBe(2500);
    expect(stress.clusters.length).toBeGreaterThan(0);
    expect(stress.clusters.every((cluster) => cluster.memberNodeIds.length > 0)).toBe(true);
  });
});
