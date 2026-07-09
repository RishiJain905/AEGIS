import { describe, expect, it } from 'vitest';

import {
  dprForTier,
  probeCapabilityReport,
  recommendQualityTier,
} from '@/features/cinematic-graph/lib/capability';
import { RenderQualityTier } from '@/features/cinematic-graph/contracts';
import { clusterZ, resolveStablePositions } from '@/features/cinematic-graph/lib/stable-positions';
import type { GraphNodeV1 } from '@aegis/contracts-ts';

describe('cinematic capability probing', () => {
  it('recommends fallback2d when WebGL is unavailable', () => {
    const report = probeCapabilityReport({
      forceWebglUnavailable: true,
      reducedMotion: false,
    });
    expect(report.webglAvailable).toBe(false);
    expect(report.recommendedTier).toBe(RenderQualityTier.FALLBACK_2D);
    expect(report.reasonCodes).toContain('webgl-unavailable');
  });

  it('respects reduced motion without inventing domain facts', () => {
    const recommendation = recommendQualityTier({
      webglAvailable: true,
      reducedMotion: true,
      estimatedDeviceMemoryGb: 16,
    });
    expect(recommendation.tier).toBe(RenderQualityTier.MEDIUM);
    expect(recommendation.reasonCodes).toContain('reduced-motion');
  });

  it('caps device pixel ratio by quality tier', () => {
    expect(dprForTier(RenderQualityTier.HIGH, 3)).toBe(1.75);
    expect(dprForTier(RenderQualityTier.MEDIUM, 3)).toBe(1.25);
    expect(dprForTier(RenderQualityTier.LOW, 3)).toBe(1);
    expect(dprForTier(RenderQualityTier.FALLBACK_2D, 3)).toBe(1);
  });
});

describe('stable 3D positions', () => {
  it('derives deterministic z from cluster id and preserves xy across calls', () => {
    const nodes = [
      {
        schemaVersion: 1,
        id: 'asset:a',
        entityType: 'asset',
        assetType: 'service',
        label: 'A',
        clusterId: 'business-unit:retail',
        riskScore: 0.2,
        criticality: 0.5,
        status: 'normal',
        revision: 1,
      },
      {
        schemaVersion: 1,
        id: 'asset:b',
        entityType: 'asset',
        assetType: 'service',
        label: 'B',
        clusterId: 'business-unit:retail',
        riskScore: 0.1,
        criticality: 0.4,
        status: 'normal',
        revision: 1,
      },
    ] as GraphNodeV1[];

    const first = resolveStablePositions(nodes, [], { 'asset:a': { x: 10, y: 20 } });
    const second = resolveStablePositions(nodes, [], { 'asset:a': { x: 10, y: 20 } });
    expect(first['asset:a']).toEqual(second['asset:a']);
    expect(first['asset:a'].x).toBe(10);
    expect(first['asset:a'].y).toBe(20);
    expect(first['asset:a'].z).toBe(clusterZ('business-unit:retail'));
    expect(first['asset:b'].z).toBe(clusterZ('business-unit:retail'));
  });
});
