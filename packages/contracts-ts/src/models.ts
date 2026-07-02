import { z } from 'zod';

import { assetIdSchema, eventIdSchema, modelIdSchema, runIdSchema, simTimestampSchema, utcTimestampSchema } from './primitives';
import {
  ANOMALY_EXPLANATION_SCHEMA_VERSION,
  MODEL_ARTIFACT_REFERENCE_SCHEMA_VERSION,
  MODEL_EVALUATE_REQUEST_SCHEMA_VERSION,
  MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION,
  MODEL_INFERENCE_RESULT_SCHEMA_VERSION,
  MODEL_VERIFY_ARTIFACT_REQUEST_SCHEMA_VERSION,
  MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
  TRAINING_RUN_MANIFEST_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const ModelApprovalStatus = {
  APPROVED: 'approved',
  PENDING: 'pending',
  REJECTED: 'rejected',
} as const;

export const AnomalyRiskBand = {
  NORMAL: 'normal',
  ELEVATED: 'elevated',
  HIGH: 'high',
} as const;

export const sourceWindowSchema = z
  .object({
    windowStartEpoch: z.number().int().min(0),
    windowEndEpoch: z.number().int().min(0),
    simTimeStart: simTimestampSchema,
    simTimeEnd: simTimestampSchema,
  })
  .strict();

export const baselineComparisonSchema = z
  .object({
    baselineVersion: z.string().min(1),
    featureName: z.string().min(1),
    observedValue: z.number(),
    baselineMean: z.number(),
    baselineStd: z.number().min(0),
    zScore: z.number(),
  })
  .strict();

export const anomalyExplanationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ANOMALY_EXPLANATION_SCHEMA_VERSION),
    summary: z.string().min(1),
    topFeatures: z.array(z.string()).min(1),
    featureContributions: z.record(z.number()),
    threshold: z.number().min(0).max(1),
    observedScore: z.number().min(0).max(1),
    sourceWindow: sourceWindowSchema,
    modelVersionId: modelIdSchema,
    modelSemanticVersion: z.string().min(1),
    comparisonBaseline: baselineComparisonSchema.optional(),
  })
  .strict();

export const modelArtifactReferenceSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_ARTIFACT_REFERENCE_SCHEMA_VERSION),
    objectKey: z.string().min(1).max(1024),
    checksum: z.string().min(1).max(128),
    contentType: z.string().min(1).max(256),
    sizeBytes: z.number().int().min(0),
    serializationFormat: z.string().min(1),
  })
  .strict();

export const trainingRunManifestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TRAINING_RUN_MANIFEST_SCHEMA_VERSION),
    trainingRunId: z.string().min(1),
    scenarioId: z.string().min(1),
    trainingSeeds: z.array(z.number().int()).min(1),
    holdoutSeeds: z.array(z.number().int()).min(1),
    featureSchemaVersion: z.number().int().min(1),
    datasetIds: z.array(z.string()).default([]),
    hyperparameters: z.record(z.unknown()).default({}),
    randomSeed: z.number().int().min(0),
    codeRevision: z.string().min(1),
    sklearnVersion: z.string().min(1),
    vectorCount: z.number().int().min(0),
    splitPolicy: z.string().min(1),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const riskBandThresholdsSchema = z
  .object({
    elevated: z.number().min(0).max(1),
    high: z.number().min(0).max(1),
  })
  .strict();

export const modelInferenceResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_INFERENCE_RESULT_SCHEMA_VERSION),
    entityId: assetIdSchema,
    score: z.number().min(0).max(1),
    threshold: z.number().min(0).max(1),
    riskBand: z.enum(['normal', 'elevated', 'high']),
    explanation: anomalyExplanationSchema,
    deduplicationKey: z.string().min(1),
    sourceEventId: eventIdSchema.optional(),
    isAnomaly: z.boolean(),
  })
  .strict();

export const modelScoreRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_EVALUATE_REQUEST_SCHEMA_VERSION),
    runId: runIdSchema,
    fromSequence: z.number().int().min(1).optional(),
    toSequence: z.number().int().min(1).optional(),
    dryRun: z.boolean().default(false),
  })
  .strict();

export const modelScoreResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION),
    runId: runIdSchema,
    modelVersionId: modelIdSchema.optional(),
    scoresComputed: z.number().int().min(0),
    anomaliesDetected: z.number().int().min(0),
    alertsPersisted: z.number().int().min(0),
    scoresSuppressed: z.number().int().min(0),
    fallbackActive: z.boolean(),
    fallbackReason: z.string().optional(),
    results: z.array(modelInferenceResultSchema).default([]),
    deterministicChecksum: z.string().min(1),
  })
  .strict();

export const modelVerifyArtifactRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_VERIFY_ARTIFACT_REQUEST_SCHEMA_VERSION),
    manifestPath: z.string().min(1),
    artifactPath: z.string().optional(),
  })
  .strict();

export const modelVerifyArtifactResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION),
    valid: z.boolean(),
    checksumMatch: z.boolean(),
    schemaCompatible: z.boolean(),
    approvalStatus: z.enum(['approved', 'pending', 'rejected']).optional(),
    errorCode: z.string().optional(),
    errorMessage: z.string().optional(),
  })
  .strict();

export type SourceWindowV1 = z.infer<typeof sourceWindowSchema>;
export type BaselineComparisonV1 = z.infer<typeof baselineComparisonSchema>;
export type AnomalyExplanationV1 = z.infer<typeof anomalyExplanationSchema>;
export type ModelArtifactReferenceV1 = z.infer<typeof modelArtifactReferenceSchema>;
export type TrainingRunManifestV1 = z.infer<typeof trainingRunManifestSchema>;
export type RiskBandThresholdsV1 = z.infer<typeof riskBandThresholdsSchema>;
export type ModelInferenceResultV1 = z.infer<typeof modelInferenceResultSchema>;
export type ModelScoreRequestV1 = z.infer<typeof modelScoreRequestSchema>;
export type ModelScoreResponseV1 = z.infer<typeof modelScoreResponseSchema>;
export type ModelVerifyArtifactRequestV1 = z.infer<typeof modelVerifyArtifactRequestSchema>;
export type ModelVerifyArtifactResponseV1 = z.infer<typeof modelVerifyArtifactResponseSchema>;
