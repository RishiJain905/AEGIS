import { z } from 'zod';

import { RelationshipType } from './graph';
import { assetIdSchema, edgeIdSchema, runIdSchema, simTimestampSchema } from './primitives';
import {
  ASSET_RISK_SCORE_SCHEMA_VERSION,
  RISK_COMPUTE_REQUEST_SCHEMA_VERSION,
  RISK_COMPUTE_RESPONSE_SCHEMA_VERSION,
  RISK_CONTRIBUTION_SCHEMA_VERSION,
  RISK_ENGINE_CONFIG_SCHEMA_VERSION,
  RISK_EXPLANATION_PATH_SCHEMA_VERSION,
  RISK_INPUT_SCHEMA_VERSION,
  RISK_PROJECTION_DELTA_SCHEMA_VERSION,
  RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const GRAPH_RISK_ALGORITHM_VERSION = 'graph-risk-v1' as const;

export const RiskSignalSourceType = {
  RULE: 'rule',
  MODEL: 'model',
} as const;

export const RiskSignalStatus = {
  ACTIVE: 'active',
  RESOLVED: 'resolved',
  EXPIRED: 'expired',
} as const;

export const riskInputSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_INPUT_SCHEMA_VERSION),
    signalId: z.string().min(1),
    runId: runIdSchema,
    sourceType: z.enum([RiskSignalSourceType.RULE, RiskSignalSourceType.MODEL]),
    assetId: assetIdSchema,
    strength: z.number().min(0).max(1),
    confidence: z.number().min(0).max(1),
    simTime: simTimestampSchema,
    deduplicationKey: z.string().min(1),
    status: z
      .enum([RiskSignalStatus.ACTIVE, RiskSignalStatus.RESOLVED, RiskSignalStatus.EXPIRED])
      .default(RiskSignalStatus.ACTIVE),
    provenanceRef: z.string().min(1),
    detectorId: z.string().optional(),
    ruleId: z.string().optional(),
  })
  .strict();

export const riskEngineConfigSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_ENGINE_CONFIG_SCHEMA_VERSION),
    algorithmVersion: z.literal(GRAPH_RISK_ALGORITHM_VERSION),
    globalCap: z.number().min(0).max(1).default(1),
    maxHops: z.number().int().min(1).max(16).default(4),
    distanceDecayFactor: z.number().min(0).max(1).default(0.65),
    temporalDecayFactor: z.number().min(0).max(1).default(0.5),
    temporalHalfLifeSeconds: z.number().positive().default(3600),
    criticalityAmplifier: z.number().min(0).max(1).default(0.25),
    minExplanationContribution: z.number().min(0).max(1).default(0.01),
    relationshipTypeWeights: z
      .record(z.number().min(0).max(1))
      .default(() =>
        Object.fromEntries(Object.values(RelationshipType).map((value) => [value, 1])),
      ),
    eligibleRelationshipTypes: z
      .array(z.nativeEnum(RelationshipType))
      .default(() => Object.values(RelationshipType)),
    topExplanationPaths: z.number().int().min(1).max(20).default(5),
  })
  .strict();

export const riskPathHopSchema = z
  .object({
    edgeId: edgeIdSchema,
    sourceId: assetIdSchema,
    targetId: assetIdSchema,
    relationshipType: z.nativeEnum(RelationshipType),
    edgeWeight: z.number().min(0).max(1),
    hopIndex: z.number().int().min(1),
  })
  .strict();

export const riskExplanationPathSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_EXPLANATION_PATH_SCHEMA_VERSION),
    signalId: z.string().min(1),
    originAssetId: assetIdSchema,
    targetAssetId: assetIdSchema,
    nodeIds: z.array(assetIdSchema).min(1),
    hops: z.array(riskPathHopSchema),
    hopCount: z.number().int().min(0),
    distanceDecay: z.number().min(0).max(1),
    temporalDecay: z.number().min(0).max(1),
    criticalityFactor: z.number().min(1),
    contribution: z.number().min(0).max(1),
    algorithmVersion: z.string().min(1),
  })
  .strict();

export const riskContributionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_CONTRIBUTION_SCHEMA_VERSION),
    signalId: z.string().min(1),
    originAssetId: assetIdSchema,
    targetAssetId: assetIdSchema,
    amount: z.number().min(0).max(1),
    hopCount: z.number().int().min(0),
    distanceDecay: z.number().min(0).max(1),
    temporalDecay: z.number().min(0).max(1),
    criticalityFactor: z.number().min(1),
    explanationPath: riskExplanationPathSchema,
  })
  .strict();

export const assetRiskScoreSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ASSET_RISK_SCORE_SCHEMA_VERSION),
    runId: runIdSchema,
    assetId: assetIdSchema,
    total: z.number().min(0).max(1),
    direct: z.number().min(0).max(1),
    propagated: z.number().min(0).max(1),
    algorithmVersion: z.string().min(1),
    computedAtSequence: z.number().int().min(0),
    simTime: simTimestampSchema,
    topContributions: z.array(riskContributionSchema).default([]),
  })
  .strict()
  .refine((value) => value.total <= value.direct + value.propagated + 1e-9, {
    message: 'Total risk cannot exceed direct + propagated decomposition',
  });

export const riskProjectionNodeUpdateSchema = z
  .object({
    assetId: assetIdSchema,
    riskScore: z.number().min(0).max(1),
    direct: z.number().min(0).max(1),
    propagated: z.number().min(0).max(1),
    revision: z.number().int().min(0),
  })
  .strict();

export const riskProjectionDeltaSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_PROJECTION_DELTA_SCHEMA_VERSION),
    runId: runIdSchema,
    sequence: z.number().int().min(0),
    algorithmVersion: z.string().min(1),
    nodeUpdates: z.array(riskProjectionNodeUpdateSchema).min(1),
  })
  .strict();

export const riskComputeRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_COMPUTE_REQUEST_SCHEMA_VERSION),
    runId: runIdSchema,
    fromSequence: z.number().int().min(0).optional(),
    toSequence: z.number().int().min(0).optional(),
    dryRun: z.boolean().default(false),
    incidentSeedAssetIds: z.array(assetIdSchema).optional(),
  })
  .strict();

export const riskComputeResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_COMPUTE_RESPONSE_SCHEMA_VERSION),
    runId: runIdSchema,
    algorithmVersion: z.string().min(1),
    scoresComputed: z.number().int().min(0),
    nodesUpdated: z.number().int().min(0),
    eventsPersisted: z.number().int().min(0),
    checksum: z.string().min(1),
  })
  .strict();

export const riskScoresListResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION),
    runId: runIdSchema,
    scores: z.array(assetRiskScoreSchema),
  })
  .strict();

export type RiskInputV1 = z.infer<typeof riskInputSchema>;
export type RiskEngineConfigV1 = z.infer<typeof riskEngineConfigSchema>;
export type RiskExplanationPathV1 = z.infer<typeof riskExplanationPathSchema>;
export type RiskContributionV1 = z.infer<typeof riskContributionSchema>;
export type AssetRiskScoreV1 = z.infer<typeof assetRiskScoreSchema>;
export type RiskProjectionDeltaV1 = z.infer<typeof riskProjectionDeltaSchema>;
export type RiskComputeRequestV1 = z.infer<typeof riskComputeRequestSchema>;
export type RiskComputeResponseV1 = z.infer<typeof riskComputeResponseSchema>;
export type RiskScoresListResponseV1 = z.infer<typeof riskScoresListResponseSchema>;
