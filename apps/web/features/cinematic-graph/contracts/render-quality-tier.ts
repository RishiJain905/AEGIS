import { z } from 'zod';

export const RENDER_QUALITY_TIER_SCHEMA_VERSION = 1;

export const RenderQualityTier = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
  FALLBACK_2D: 'fallback2d',
} as const;

export type RenderQualityTierValue =
  (typeof RenderQualityTier)[keyof typeof RenderQualityTier];

export const renderQualityTierSchema = z.enum([
  RenderQualityTier.HIGH,
  RenderQualityTier.MEDIUM,
  RenderQualityTier.LOW,
  RenderQualityTier.FALLBACK_2D,
]);

export function assertExhaustiveRenderQualityTier(value: never): never {
  throw new Error(`Unhandled render quality tier: ${String(value)}`);
}
