import { z } from 'zod';

import { authoredIdSchema, eventIdSchema, runIdSchema, sequenceSchema } from './primitives';
import {
  DATASET_MANIFEST_SCHEMA_VERSION,
  FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION,
  FEATURE_VECTOR_SCHEMA_VERSION,
  FEATURE_WINDOW_SCHEMA_VERSION,
  ONLINE_FEATURE_UPDATE_SCHEMA_VERSION,
} from './versioning';

export const TRANSFORM_VERSION = '0.0.0-phase14' as const;
export const DEFAULT_WINDOW_DURATION_SIM_SECONDS = 300;

export const FeatureErrorCode = {
  VALIDATION_FAILED: 'FEATURE_VALIDATION_FAILED',
  UNSUPPORTED_EVENT: 'FEATURE_UNSUPPORTED_EVENT',
  DUPLICATE_EVENT: 'FEATURE_DUPLICATE_EVENT',
  OUT_OF_ORDER: 'FEATURE_OUT_OF_ORDER',
  LATE_EVENT: 'FEATURE_LATE_EVENT',
  HIDDEN_TRUTH_BLOCKED: 'FEATURE_HIDDEN_TRUTH_BLOCKED',
  SCHEMA_MISMATCH: 'FEATURE_SCHEMA_MISMATCH',
  MALFORMED_PAYLOAD: 'FEATURE_MALFORMED_PAYLOAD',
} as const;

export const featureErrorCodeSchema = z.enum([
  'FEATURE_VALIDATION_FAILED',
  'FEATURE_UNSUPPORTED_EVENT',
  'FEATURE_DUPLICATE_EVENT',
  'FEATURE_OUT_OF_ORDER',
  'FEATURE_LATE_EVENT',
  'FEATURE_HIDDEN_TRUTH_BLOCKED',
  'FEATURE_SCHEMA_MISMATCH',
  'FEATURE_MALFORMED_PAYLOAD',
]);

export const featureDataTypeSchema = z.enum(['float', 'int', 'categorical']);

export const featureDefinitionSchema = z
  .object({
    name: z.string().min(1).max(128),
    orderIndex: z.number().int().min(0),
    dtype: featureDataTypeSchema,
    unit: z.string().min(1).max(64),
    minValue: z.number().nullable().optional(),
    maxValue: z.number().nullable().optional(),
    missingSentinel: z.number(),
    categoricalMappingVersion: z.number().int().min(1).nullable().optional(),
    categoricalValues: z.array(z.string()).nullable().optional(),
  })
  .strict();

export const featureSchemaManifestSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    featureSchemaVersion: z.number().int().min(1),
    transformVersion: z.string().min(1),
    windowDurationSimSeconds: z.number().int().min(1),
    features: z.array(featureDefinitionSchema).min(1),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported feature schema manifest version: ${String(value.schemaVersion)}`,
      });
    }
    const indices = value.features.map((feature) => feature.orderIndex);
    if (indices.join(',') !== [...indices].sort((a, b) => a - b).join(',')) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Feature definitions must be sorted by orderIndex',
      });
    }
    if (new Set(indices).size !== indices.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Feature orderIndex values must be unique',
      });
    }
  });

export const featureProvenanceSchema = z
  .object({
    runId: runIdSchema,
    entityId: authoredIdSchema,
    sequenceStart: sequenceSchema,
    sequenceEnd: sequenceSchema,
    simTimeStart: z.string().min(1),
    simTimeEnd: z.string().min(1),
    featureSchemaVersion: z.number().int().min(1),
    transformVersion: z.string().min(1),
    sourceEventIds: z.array(eventIdSchema),
  })
  .strict();

export const featureWindowSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    windowKey: z.string().min(1),
    runId: runIdSchema,
    entityId: authoredIdSchema,
    windowStartSimTime: z.string().min(1),
    windowEndSimTime: z.string().min(1),
    isClosed: z.boolean(),
    watermarkSequence: sequenceSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== FEATURE_WINDOW_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported feature window schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const featureVectorSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    featureSchemaVersion: z.number().int().min(1),
    windowKey: z.string().min(1),
    entityId: authoredIdSchema,
    values: z.array(z.number()),
    provenance: featureProvenanceSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== FEATURE_VECTOR_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported feature vector schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const datasetSourceRunSchema = z
  .object({
    runId: runIdSchema,
    seed: z.number().int(),
    scenarioVersionId: authoredIdSchema,
  })
  .strict();

export const datasetManifestSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    datasetChecksum: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    featureSchemaVersion: z.number().int().min(1),
    transformVersion: z.string().min(1),
    rowCount: z.number().int().min(0),
    sourceRuns: z.array(datasetSourceRunSchema).min(1),
    windowDurationSimSeconds: z.number().int().min(1),
    createdAt: z.string().min(1),
    workspaceVersion: z.string().min(1),
    compatibilityMetadata: z.record(z.string(), z.unknown()).optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== DATASET_MANIFEST_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported dataset manifest schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const featureRejectionSchema = z
  .object({
    eventId: eventIdSchema,
    sequence: sequenceSchema,
    code: featureErrorCodeSchema,
    message: z.string().min(1),
  })
  .strict();

export const onlineFeatureUpdateSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    windowKey: z.string().min(1),
    vector: featureVectorSchema,
    lastProcessedSequence: sequenceSchema,
    rejections: z.array(featureRejectionSchema).optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== ONLINE_FEATURE_UPDATE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported online feature update schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const featureComputeRequestSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    fromSequence: sequenceSchema.optional(),
    toSequence: sequenceSchema.optional(),
    mode: z.enum(['incremental', 'full']).default('full'),
  })
  .strict();

export const featureComputeResponseSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    vectors: z.array(featureVectorSchema),
    windows: z.array(featureWindowSchema),
    rejections: z.array(featureRejectionSchema),
    lastProcessedSequence: sequenceSchema,
    outputChecksum: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  })
  .strict();

export const featureParityCheckResponseSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    matching: z.boolean(),
    offlineChecksum: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    onlineChecksum: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    vectorCount: z.number().int().min(0),
    rejectionCount: z.number().int().min(0),
  })
  .strict();

export type FeatureSchemaManifestV1 = z.infer<typeof featureSchemaManifestSchema>;
export type FeatureVectorV1 = z.infer<typeof featureVectorSchema>;
export type FeatureWindowV1 = z.infer<typeof featureWindowSchema>;
export type FeatureProvenanceV1 = z.infer<typeof featureProvenanceSchema>;
export type DatasetManifestV1 = z.infer<typeof datasetManifestSchema>;
export type OnlineFeatureUpdateV1 = z.infer<typeof onlineFeatureUpdateSchema>;
