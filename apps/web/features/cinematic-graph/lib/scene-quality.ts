import { RenderQualityTier, type RenderQualityTierValue } from '../contracts';

export interface SceneQualityProfile {
  nodeSegments: number;
  material: 'physical' | 'standard';
  glow: boolean;
  shadows: boolean;
  fogNear: number;
  fogFar: number;
  edgeWidthScale: number;
}

const profiles: Record<RenderQualityTierValue, SceneQualityProfile> = {
  [RenderQualityTier.HIGH]: {
    nodeSegments: 28,
    material: 'physical',
    glow: true,
    shadows: true,
    fogNear: 850,
    fogFar: 3_400,
    edgeWidthScale: 1.2,
  },
  [RenderQualityTier.MEDIUM]: {
    nodeSegments: 18,
    material: 'standard',
    glow: true,
    shadows: false,
    fogNear: 900,
    fogFar: 3_200,
    edgeWidthScale: 1,
  },
  [RenderQualityTier.LOW]: {
    nodeSegments: 10,
    material: 'standard',
    glow: false,
    shadows: false,
    fogNear: 1_000,
    fogFar: 3_000,
    edgeWidthScale: 0.8,
  },
  [RenderQualityTier.FALLBACK_2D]: {
    nodeSegments: 8,
    material: 'standard',
    glow: false,
    shadows: false,
    fogNear: 1_000,
    fogFar: 3_000,
    edgeWidthScale: 0.8,
  },
};

export function getSceneQualityProfile(tier: RenderQualityTierValue): SceneQualityProfile {
  return profiles[tier];
}

export function getSceneFrameloop(
  tier: RenderQualityTierValue,
  reducedMotion: boolean,
): 'always' | 'demand' {
  return tier === RenderQualityTier.LOW || reducedMotion ? 'demand' : 'always';
}
