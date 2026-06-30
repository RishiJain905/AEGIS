import { z } from 'zod';

export const LOD_POLICY_SCHEMA_VERSION = 1 as const;

export const LabelMode = {
  ALL: 'all',
  SELECTED: 'selected',
  NONE: 'none',
} as const;

export type LabelModeValue = (typeof LabelMode)[keyof typeof LabelMode];

export const labelModeSchema = z.enum([LabelMode.ALL, LabelMode.SELECTED, LabelMode.NONE]);

export const lodTierSchema = z
  .object({
    id: z.string(),
    minNodeCount: z.number().int().nonnegative(),
    minEdgeCount: z.number().int().nonnegative(),
    maxZoomRatio: z.number().positive().optional(),
    maxVisibleEdges: z.number().int().nonnegative(),
    labelMode: labelModeSchema,
    clusterCollapseThreshold: z.number().int().nonnegative(),
    edgeOpacityFloor: z.number().min(0).max(1),
    labelRenderedSizeThreshold: z.number().positive(),
    labelDensity: z.number().min(0).max(1),
    renderEdgeLabels: z.boolean(),
  })
  .strict();

export type LodTier = z.infer<typeof lodTierSchema>;

export const lodPolicySchema = z
  .object({
    schemaVersion: z.literal(LOD_POLICY_SCHEMA_VERSION),
    tiers: z.array(lodTierSchema).min(1),
  })
  .strict();

export type LodPolicy = z.infer<typeof lodPolicySchema>;

export const defaultLodPolicy: LodPolicy = {
  schemaVersion: LOD_POLICY_SCHEMA_VERSION,
  tiers: [
    {
      id: 'detail',
      minNodeCount: 0,
      minEdgeCount: 0,
      maxVisibleEdges: Number.POSITIVE_INFINITY,
      labelMode: LabelMode.ALL,
      clusterCollapseThreshold: Number.POSITIVE_INFINITY,
      edgeOpacityFloor: 0.4,
      labelRenderedSizeThreshold: 6,
      labelDensity: 0.5,
      renderEdgeLabels: false,
    },
    {
      id: 'balanced',
      minNodeCount: 200,
      minEdgeCount: 400,
      maxVisibleEdges: 1500,
      labelMode: LabelMode.SELECTED,
      clusterCollapseThreshold: 50,
      edgeOpacityFloor: 0.25,
      labelRenderedSizeThreshold: 10,
      labelDensity: 0.35,
      renderEdgeLabels: false,
    },
    {
      id: 'overview',
      minNodeCount: 800,
      minEdgeCount: 1600,
      maxVisibleEdges: 600,
      labelMode: LabelMode.SELECTED,
      clusterCollapseThreshold: 20,
      edgeOpacityFloor: 0.15,
      labelRenderedSizeThreshold: 14,
      labelDensity: 0.2,
      renderEdgeLabels: false,
    },
    {
      id: 'dense',
      minNodeCount: 1500,
      minEdgeCount: 3000,
      maxVisibleEdges: 300,
      labelMode: LabelMode.NONE,
      clusterCollapseThreshold: 10,
      edgeOpacityFloor: 0.1,
      labelRenderedSizeThreshold: 20,
      labelDensity: 0.1,
      renderEdgeLabels: false,
    },
  ],
};

export const lodRenderHintsSchema = z
  .object({
    tierId: z.string(),
    maxVisibleEdges: z.number().int().nonnegative(),
    labelMode: labelModeSchema,
    clusterCollapseThreshold: z.number().int().nonnegative(),
    edgeOpacityFloor: z.number().min(0).max(1),
    labelRenderedSizeThreshold: z.number().positive(),
    labelDensity: z.number().min(0).max(1),
    renderEdgeLabels: z.boolean(),
    visibleEdgeIds: z.array(z.string()),
    collapsedClusterIds: z.array(z.string()),
  })
  .strict();

export type LodRenderHints = z.infer<typeof lodRenderHintsSchema>;

export function parseLodPolicy(data: unknown): LodPolicy {
  return lodPolicySchema.parse(data);
}

export function resolveLodTier(
  policy: LodPolicy,
  visibleNodeCount: number,
  visibleEdgeCount: number,
  zoomRatio = 1,
): LodTier {
  const sorted = [...policy.tiers].sort((a, b) => {
    const scoreA = a.minNodeCount + a.minEdgeCount;
    const scoreB = b.minNodeCount + b.minEdgeCount;
    return scoreB - scoreA;
  });

  for (const tier of sorted) {
    const zoomOk = tier.maxZoomRatio === undefined || zoomRatio >= tier.maxZoomRatio;
    if (visibleNodeCount >= tier.minNodeCount && visibleEdgeCount >= tier.minEdgeCount && zoomOk) {
      return tier;
    }
  }

  const fallback = policy.tiers[0];
  if (!fallback) {
    throw new Error('LOD policy must define at least one tier');
  }
  return fallback;
}
