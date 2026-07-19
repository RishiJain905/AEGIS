import { describe, expect, it } from 'vitest';

import { RenderQualityTier } from '@/features/cinematic-graph/contracts';
import {
  getSceneFrameloop,
  getSceneQualityProfile,
} from '@/features/cinematic-graph/lib/scene-quality';

describe('cinematic scene quality', () => {
  it('gates expensive presentation details by quality tier', () => {
    expect(getSceneQualityProfile(RenderQualityTier.HIGH)).toMatchObject({
      nodeSegments: 28,
      material: 'physical',
      glow: true,
      shadows: true,
    });
    expect(getSceneQualityProfile(RenderQualityTier.LOW)).toMatchObject({
      nodeSegments: 10,
      material: 'standard',
      glow: false,
      shadows: false,
    });
  });

  it('uses static demand rendering for low tier or reduced motion', () => {
    expect(getSceneFrameloop(RenderQualityTier.HIGH, false)).toBe('always');
    expect(getSceneFrameloop(RenderQualityTier.HIGH, true)).toBe('demand');
    expect(getSceneFrameloop(RenderQualityTier.LOW, false)).toBe('demand');
  });
});
