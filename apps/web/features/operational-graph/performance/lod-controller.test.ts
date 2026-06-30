import { describe, expect, it } from 'vitest';

import { buildLodRenderHints } from './lod-controller';

describe('lod controller', () => {
  it('reduces visible edges at higher density tiers', () => {
    const hints = buildLodRenderHints({
      visibleNodeIds: Array.from({ length: 1600 }, (_, index) => `asset:n-${String(index)}`),
      visibleEdgeIds: Array.from({ length: 3200 }, (_, index) => `edge:e-${String(index)}`),
      highlightedEdgeIds: ['edge:e-1'],
      collapsedClusterIds: [],
    });

    expect(hints.tierId).toBe('dense');
    expect(hints.visibleEdgeIds.length).toBeLessThan(3200);
    expect(hints.visibleEdgeIds[0]).toBe('edge:e-1');
  });
});
