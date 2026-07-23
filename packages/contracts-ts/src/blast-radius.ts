import { z } from 'zod';

import { assetIdSchema, runIdSchema } from './primitives';
import { scenarioCommandTemplateSchema } from './proposals';
import { BLAST_RADIUS_PREVIEW_SCHEMA_VERSION } from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .superRefine((value, ctx) => {
      if (value !== expected) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Unsupported schema version: ${String(value)}`,
        });
      }
    });

const actionClassSchema = z.enum(['class_0', 'class_1', 'class_2', 'class_3']);

export const blastRadiusImpactKindSchema = z.enum(['severed', 'degraded', 'outage']);

export type BlastRadiusImpactKindV1 = z.infer<typeof blastRadiusImpactKindSchema>;

// A single 1-hop neighbour affected by a containment action, via one graph edge.
export const blastRadiusImpactSchema = z
  .object({
    assetId: assetIdSchema,
    label: z.string(),
    criticality: z.number().min(0).max(1),
    status: z.string(),
    relationshipType: z.string(),
    impactKind: blastRadiusImpactKindSchema,
    edgeId: z.string(),
  })
  .strict();

export type BlastRadiusImpactV1 = z.infer<typeof blastRadiusImpactSchema>;

// A service reached transitively through the dependency chain from the target.
export const blastRadiusDownstreamSchema = z
  .object({
    assetId: assetIdSchema,
    label: z.string(),
    criticality: z.number().min(0).max(1),
    hops: z.number().int().min(1),
  })
  .strict();

export type BlastRadiusDownstreamV1 = z.infer<typeof blastRadiusDownstreamSchema>;

// Projected collateral of a containment (command, target) over the current graph.
export const blastRadiusPreviewSchema = z
  .object({
    schemaVersion: schemaVersionCheck(BLAST_RADIUS_PREVIEW_SCHEMA_VERSION),
    runId: runIdSchema,
    command: scenarioCommandTemplateSchema,
    targetAssetId: assetIdSchema,
    actionClass: actionClassSchema,
    severedEdgeCount: z.number().int().min(0),
    degradedEdgeCount: z.number().int().min(0),
    impactedAssets: z.array(blastRadiusImpactSchema).default([]),
    downstreamAssets: z.array(blastRadiusDownstreamSchema).default([]),
    warnings: z.array(z.string()).default([]),
  })
  .strict();

export type BlastRadiusPreviewV1 = z.infer<typeof blastRadiusPreviewSchema>;
