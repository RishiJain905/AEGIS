import { z } from 'zod';

import {
  assetIdSchema,
  authoredIdSchema,
  eventIdSchema,
  runIdSchema,
  simTimestampSchema,
  utcTimestampSchema,
} from './primitives';
import {
  ALERT_CANDIDATE_SCHEMA_VERSION,
  DETECTION_RULE_REGISTRY_SCHEMA_VERSION,
  DETECTION_RULE_SCHEMA_VERSION,
  EVALUATION_RUN_SCHEMA_VERSION,
  METRIC_REPORT_SCHEMA_VERSION,
  RULE_EVALUATION_SCHEMA_VERSION,
  RULE_EXPLANATION_SCHEMA_VERSION,
  RULE_THRESHOLD_SCHEMA_VERSION,
  STATISTICAL_BASELINE_MANIFEST_SCHEMA_VERSION,
  STATISTICAL_BASELINE_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const DetectorType = {
  DETERMINISTIC: 'deterministic',
  STATISTICAL_BASELINE: 'statistical_baseline',
} as const;

export const ThresholdOperator = {
  GTE: 'gte',
  GT: 'gt',
  LTE: 'lte',
  LT: 'lt',
  EQ: 'eq',
} as const;

export const BaselineMethod = {
  ROLLING_MEAN_STD: 'rolling_mean_std',
} as const;

export const RuleEvaluationStatus = {
  FIRED: 'fired',
  SKIPPED: 'skipped',
  ERROR: 'error',
} as const;

export const ruleThresholdSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RULE_THRESHOLD_SCHEMA_VERSION),
    featureName: z.string().min(1),
    operator: z.enum(['gte', 'gt', 'lte', 'lt', 'eq']),
    value: z.number(),
    minCount: z.number().optional(),
  })
  .strict();

export const detectionRuleSchema = z
  .object({
    schemaVersion: schemaVersionCheck(DETECTION_RULE_SCHEMA_VERSION),
    ruleId: z.string().min(1),
    ruleVersion: z.string().min(1),
    detectorType: z.enum(['deterministic', 'statistical_baseline']),
    title: z.string().min(1),
    description: z.string().min(1),
    inputFeatures: z.array(z.string().min(1)).min(1),
    thresholds: z.array(ruleThresholdSchema).min(1),
    severity: z.string().min(1),
    confidenceBase: z.number().min(0).max(1),
    cooldownSimSeconds: z.number().int().min(0),
    suppressionGroup: z.string().optional(),
    enabled: z.boolean().default(true),
  })
  .strict();

export const detectionRuleRegistrySchema = z
  .object({
    schemaVersion: schemaVersionCheck(DETECTION_RULE_REGISTRY_SCHEMA_VERSION),
    registryVersion: z.string().min(1),
    thresholdConfigVersion: z.string().min(1),
    rules: z.array(detectionRuleSchema).min(1),
  })
  .strict();

export const statisticalBaselineEntrySchema = z
  .object({
    featureName: z.string().min(1),
    entityId: authoredIdSchema.optional(),
    mean: z.number(),
    std: z.number(),
    sampleCount: z.number().int().min(0),
    zScoreThreshold: z.number().min(0),
  })
  .strict();

export const statisticalBaselineSchema = z
  .object({
    schemaVersion: schemaVersionCheck(STATISTICAL_BASELINE_SCHEMA_VERSION),
    baselineVersion: z.string().min(1),
    method: z.enum(['rolling_mean_std']),
    trainingSeeds: z.array(z.number().int()).min(1),
    featureSchemaVersion: z.number().int().min(1),
    entries: z.array(statisticalBaselineEntrySchema).min(1),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const statisticalBaselineManifestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(STATISTICAL_BASELINE_MANIFEST_SCHEMA_VERSION),
    baselineVersion: z.string().min(1),
    baselineChecksum: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    trainingSeeds: z.array(z.number().int()).min(1),
    holdoutSeeds: z.array(z.number().int()).min(1),
    featureSchemaVersion: z.number().int().min(1),
    workspaceVersion: z.string().min(1),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const ruleExplanationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RULE_EXPLANATION_SCHEMA_VERSION),
    summary: z.string().min(1),
    condition: z.string().min(1),
    featureName: z.string().min(1),
    observed: z.number(),
    baseline: z.number().nullable().optional(),
    threshold: z.number(),
    comparison: z.string().min(1),
    windowKey: z.string().min(1),
    detectorType: z.enum(['deterministic', 'statistical_baseline']),
  })
  .strict();

export const alertEvidenceSchema = z
  .object({
    featureSchemaVersion: z.number().int().min(1),
    featureValues: z.record(z.string(), z.number()),
    sourceEventIds: z.array(eventIdSchema),
    windowKey: z.string().min(1),
    sequenceStart: z.number().int().min(0),
    sequenceEnd: z.number().int().min(0),
    simTimeStart: simTimestampSchema,
    simTimeEnd: simTimestampSchema,
  })
  .strict();

export const alertCandidateSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ALERT_CANDIDATE_SCHEMA_VERSION),
    runId: runIdSchema,
    ruleId: z.string().min(1),
    ruleVersion: z.string().min(1),
    detectorId: z.string().min(1),
    detectorVersion: z.string().min(1),
    detectorType: z.enum(['deterministic', 'statistical_baseline']),
    entityId: assetIdSchema,
    title: z.string().min(1),
    severity: z.string().min(1),
    confidence: z.number().min(0).max(1),
    observedValue: z.number(),
    baselineValue: z.number().nullable().optional(),
    threshold: z.number(),
    sourceWindowKey: z.string().min(1),
    deduplicationKey: z.string().min(1),
    explanation: ruleExplanationSchema,
    evidence: alertEvidenceSchema,
    sourceEventId: eventIdSchema,
  })
  .strict();

export const ruleEvaluationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RULE_EVALUATION_SCHEMA_VERSION),
    ruleId: z.string().min(1),
    status: z.enum(['fired', 'skipped', 'error']),
    candidate: alertCandidateSchema.optional(),
    errorCode: z.string().optional(),
    errorMessage: z.string().optional(),
  })
  .strict();

export const evaluationSeedMetricsSchema = z
  .object({
    seed: z.number().int(),
    runId: runIdSchema.optional(),
    precision: z.number().min(0).max(1),
    recall: z.number().min(0).max(1),
    falsePositiveRate: z.number().min(0).max(1),
    detectionDelaySimSeconds: z.number().min(0).optional(),
    causeCoverage: z.number().min(0).max(1),
    truePositives: z.number().int().min(0),
    falsePositives: z.number().int().min(0),
    falseNegatives: z.number().int().min(0),
  })
  .strict();

export const metricReportSchema = z
  .object({
    schemaVersion: schemaVersionCheck(METRIC_REPORT_SCHEMA_VERSION),
    precision: z.number().min(0).max(1),
    recall: z.number().min(0).max(1),
    falsePositiveRate: z.number().min(0).max(1),
    meanDetectionDelaySimSeconds: z.number().min(0).optional(),
    causeCoverage: z.number().min(0).max(1),
    perSeed: z.array(evaluationSeedMetricsSchema).min(1),
  })
  .strict();

export const evaluationRunSchema = z
  .object({
    schemaVersion: schemaVersionCheck(EVALUATION_RUN_SCHEMA_VERSION),
    evaluationId: z.string().min(1),
    scenarioId: z.string().min(1),
    trainingSeeds: z.array(z.number().int()).min(1),
    holdoutSeeds: z.array(z.number().int()).min(1),
    ruleRegistryVersion: z.string().min(1),
    thresholdConfigVersion: z.string().min(1),
    baselineChecksum: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    featureSchemaVersion: z.number().int().min(1),
    workspaceVersion: z.string().min(1),
    createdAt: utcTimestampSchema,
    metrics: metricReportSchema,
  })
  .strict();

export type DetectionRuleV1 = z.infer<typeof detectionRuleSchema>;
export type DetectionRuleRegistryV1 = z.infer<typeof detectionRuleRegistrySchema>;
export type StatisticalBaselineV1 = z.infer<typeof statisticalBaselineSchema>;
export type StatisticalBaselineManifestV1 = z.infer<typeof statisticalBaselineManifestSchema>;
export type RuleExplanationV1 = z.infer<typeof ruleExplanationSchema>;
export type AlertEvidenceV1 = z.infer<typeof alertEvidenceSchema>;
export type AlertCandidateV1 = z.infer<typeof alertCandidateSchema>;
export type RuleEvaluationV1 = z.infer<typeof ruleEvaluationSchema>;
export type MetricReportV1 = z.infer<typeof metricReportSchema>;
export type EvaluationRunV1 = z.infer<typeof evaluationRunSchema>;
