import { z } from 'zod';

import { RENDER_QUALITY_TIER_SCHEMA_VERSION, renderQualityTierSchema } from './render-quality-tier';

export const CAPABILITY_REPORT_SCHEMA_VERSION = 1;

export const capabilityReportSchema = z
  .object({
    schemaVersion: z.literal(CAPABILITY_REPORT_SCHEMA_VERSION),
    webglAvailable: z.boolean(),
    webgl2Available: z.boolean(),
    maxTextureSize: z.number().int().nonnegative(),
    devicePixelRatioCap: z.number().positive(),
    reducedMotion: z.boolean(),
    recommendedTier: renderQualityTierSchema,
    reasonCodes: z.array(z.string()),
    estimatedDeviceMemoryGb: z.number().positive().nullable(),
  })
  .strict();

export type CapabilityReport = z.infer<typeof capabilityReportSchema>;

export function parseCapabilityReport(data: unknown): CapabilityReport {
  return capabilityReportSchema.parse(data);
}

export const defaultCapabilityReport: CapabilityReport = {
  schemaVersion: CAPABILITY_REPORT_SCHEMA_VERSION,
  webglAvailable: false,
  webgl2Available: false,
  maxTextureSize: 0,
  devicePixelRatioCap: 1,
  reducedMotion: false,
  recommendedTier: 'fallback2d',
  reasonCodes: ['capability-not-probed'],
  estimatedDeviceMemoryGb: null,
};

void RENDER_QUALITY_TIER_SCHEMA_VERSION;
