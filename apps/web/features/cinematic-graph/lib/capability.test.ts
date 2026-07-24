import { describe, expect, it } from 'vitest';

import {
  dprForTier,
  probeCapabilityReport,
  recommendQualityTier,
} from '@/features/cinematic-graph/lib/capability';
import { RenderQualityTier } from '@/features/cinematic-graph/contracts';

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
