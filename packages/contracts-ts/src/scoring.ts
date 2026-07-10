/** Phase 29 scoring and after-action contracts. */

import { z } from 'zod';

import {
  assetIdSchema,
  eventIdSchema,
  evidenceIdSchema,
  hypothesisIdSchema,
  incidentIdSchema,
  proposalIdSchema,
  runIdSchema,
  sequenceSchema,
  utcTimestampSchema,
} from './primitives';
import {
  AFTER_ACTION_VIEW_MODEL_SCHEMA_VERSION,
  DECISION_REVIEW_SCHEMA_VERSION,
  MISSED_EVIDENCE_ITEM_SCHEMA_VERSION,
  RUN_COMPARISON_SCORE_SCHEMA_VERSION,
  RUN_SCORE_SCHEMA_VERSION,
  SCORE_COMPONENT_SCHEMA_VERSION,
  SCORE_EXPLANATION_SCHEMA_VERSION,
  SCORE_EXPORT_ARTIFACT_SCHEMA_VERSION,
  SCORE_PROVENANCE_SCHEMA_VERSION,
  SCORE_RUBRIC_SCHEMA_VERSION,
  VALID_ALTERNATIVE_SCHEMA_VERSION,
} from './versioning';

export const GRADING_ENGINE_VERSION = '1.0.0-phase29' as const;

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const scoreErrorCodeSchema = z.enum([
  'SCORE_INCOMPLETE_RUN',
  'SCORE_RUBRIC_MISSING',
  'SCORE_RUBRIC_INCOMPATIBLE',
  'SCORE_INPUT_TAMPERED',
  'SCORE_CHECKSUM_MISMATCH',
  'SCORE_NOT_FOUND',
  'SCORE_COMPARISON_INVALID',
  'SCORE_EXPORT_FAILED',
  'SCORE_VALIDATION_FAILED',
]);

export const scoreGradeBandSchema = z.enum(['A', 'B', 'C', 'D', 'F']);

export const decisionReviewOutcomeSchema = z.enum([
  'credited',
  'penalized',
  'neutral',
  'restraint_credited',
]);

export const validAlternativeKindSchema = z.enum([
  'counterfactual',
  'valid_response_branch',
  'alternative_decision',
]);

export const scoreExportFormatSchema = z.enum(['json', 'markdown']);

export const scoreExplanationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCORE_EXPLANATION_SCHEMA_VERSION),
    ruleId: z.string().min(1).max(128),
    reason: z.string().min(1).max(2048),
    eventIds: z.array(eventIdSchema).default([]),
    evidenceIds: z.array(evidenceIdSchema).default([]),
    decisionIds: z.array(z.string().min(1).max(128)).default([]),
    hypothesisIds: z.array(hypothesisIdSchema).default([]),
    proposalIds: z.array(proposalIdSchema).default([]),
    sequence: sequenceSchema.nullable().optional(),
  })
  .strict();

export const scoreRubricCriterionSchema = z
  .object({
    id: z.string().min(1).max(128),
    label: z.string().min(1).max(256),
    weight: z.number().min(0).max(1),
    description: z.string().max(1024).default(''),
  })
  .strict();

export const scoreRubricSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCORE_RUBRIC_SCHEMA_VERSION),
    scenarioId: z.string().min(1).max(128),
    scenarioVersion: z.string().min(1).max(64),
    rubricVersion: z.string().min(1).max(64),
    gradingEngineVersion: z.string().min(1).max(64),
    maxScore: z.number().positive(),
    criteria: z.array(scoreRubricCriterionSchema).min(1),
    rubricText: z.string().max(8192).default(''),
    rubricTextHash: z.string().min(1).max(128),
  })
  .strict();

export const scoreComponentSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCORE_COMPONENT_SCHEMA_VERSION),
    criterionId: z.string().min(1).max(128),
    label: z.string().min(1).max(256),
    weight: z.number().min(0).max(1),
    rawScore: z.number().min(0).max(1),
    weightedContribution: z.number().min(0),
    ruleIds: z.array(z.string().min(1).max(128)).default([]),
    explanations: z.array(scoreExplanationSchema).default([]),
  })
  .strict();

export const scoreProvenanceSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCORE_PROVENANCE_SCHEMA_VERSION),
    runId: runIdSchema,
    scenarioId: z.string().min(1).max(128),
    scenarioVersion: z.string().min(1).max(64),
    rubricVersion: z.string().min(1).max(64),
    gradingEngineVersion: z.string().min(1).max(64),
    inputEventSequenceFrom: sequenceSchema,
    inputEventSequenceTo: sequenceSchema,
    inputChecksum: z.string().min(1).max(128),
    integrityChecksum: z.string().min(1).max(128),
    calculatedAt: utcTimestampSchema,
    fingerprint: z.string().min(1).max(128),
  })
  .strict();

export const decisionReviewSchema = z
  .object({
    schemaVersion: schemaVersionCheck(DECISION_REVIEW_SCHEMA_VERSION),
    decisionId: z.string().min(1).max(128),
    kind: z.enum(['approval', 'rejection', 'modification', 'cancellation', 'agent_recommendation']),
    sequence: sequenceSchema,
    proposalId: proposalIdSchema.nullable().optional(),
    operatorAction: z.string().min(1).max(256),
    agentRecommendation: z.string().max(1024).nullable().optional(),
    availableInfoSummary: z.string().max(2048).default(''),
    availableEventIds: z.array(eventIdSchema).default([]),
    availableEvidenceIds: z.array(evidenceIdSchema).default([]),
    outcome: decisionReviewOutcomeSchema,
    scoreDelta: z.number(),
    ruleIds: z.array(z.string().min(1).max(128)).default([]),
    explanations: z.array(scoreExplanationSchema).default([]),
    usedFutureKnowledge: z.literal(false).default(false),
  })
  .strict();

export const missedEvidenceItemSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MISSED_EVIDENCE_ITEM_SCHEMA_VERSION),
    expectedEvidenceKey: z.string().min(1).max(256),
    eventType: z.string().min(1).max(128),
    assetId: assetIdSchema.nullable().optional(),
    description: z.string().max(1024).default(''),
    discovered: z.boolean(),
    relatedEventIds: z.array(eventIdSchema).default([]),
    relatedEvidenceIds: z.array(evidenceIdSchema).default([]),
    bookmarkSequence: sequenceSchema.nullable().optional(),
  })
  .strict();

export const validAlternativeSchema = z
  .object({
    schemaVersion: schemaVersionCheck(VALID_ALTERNATIVE_SCHEMA_VERSION),
    alternativeId: z.string().min(1).max(128),
    kind: validAlternativeKindSchema,
    authoritative: z.literal(false),
    label: z.string().min(1).max(256),
    description: z.string().max(2048).default(''),
    projectedOverallScore: z.number().min(0),
    scoreDelta: z.number(),
    ruleIds: z.array(z.string().min(1).max(128)).default([]),
    explanations: z.array(scoreExplanationSchema).default([]),
  })
  .strict();

export const runScoreSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RUN_SCORE_SCHEMA_VERSION),
    scoreId: z.string().min(1).max(64),
    runId: runIdSchema,
    incidentId: incidentIdSchema.nullable().optional(),
    overallScore: z.number().min(0),
    maxScore: z.number().positive(),
    grade: scoreGradeBandSchema,
    passed: z.boolean(),
    components: z.array(scoreComponentSchema).min(1),
    provenance: scoreProvenanceSchema,
    decisionReviews: z.array(decisionReviewSchema).default([]),
    missedEvidence: z.array(missedEvidenceItemSchema).default([]),
    validAlternatives: z.array(validAlternativeSchema).default([]),
    coachingText: z.string().max(8192).nullable().optional(),
    coachingAuthoritative: z.literal(false).default(false),
    hiddenCauseId: z.string().max(128).nullable().optional(),
    hiddenCauseLabel: z.string().max(256).nullable().optional(),
    hiddenCauseRevealed: z.boolean().default(false),
  })
  .strict();

export const afterActionBookmarkRefSchema = z
  .object({
    label: z.string().min(1).max(256),
    sequence: sequenceSchema,
    kind: z.enum(['detection', 'evidence', 'decision', 'missed_evidence', 'alternative', 'custom']),
    relatedId: z.string().max(128).nullable().optional(),
  })
  .strict();

export const afterActionViewModelSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AFTER_ACTION_VIEW_MODEL_SCHEMA_VERSION),
    runId: runIdSchema,
    runStatus: z.string().min(1).max(64),
    score: runScoreSchema,
    affectedAssetIds: z.array(assetIdSchema).default([]),
    lessons: z.array(z.string().min(1).max(1024)).default([]),
    scribeReportId: z.string().max(64).nullable().optional(),
    scribeVersionNumber: z.number().int().min(1).nullable().optional(),
    bookmarks: z.array(afterActionBookmarkRefSchema).default([]),
    timelineHighlights: z
      .array(
        z
          .object({
            sequence: sequenceSchema,
            label: z.string().min(1).max(512),
            kind: z.string().min(1).max(64),
            relatedId: z.string().max(128).nullable().optional(),
          })
          .strict(),
      )
      .default([]),
  })
  .strict();

export const runComparisonSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RUN_COMPARISON_SCORE_SCHEMA_VERSION),
    leftRunId: runIdSchema,
    rightRunId: runIdSchema,
    leftScoreId: z.string().min(1).max(64),
    rightScoreId: z.string().min(1).max(64),
    leftOverallScore: z.number().min(0),
    rightOverallScore: z.number().min(0),
    overallDelta: z.number(),
    componentDeltas: z
      .array(
        z
          .object({
            criterionId: z.string().min(1).max(128),
            leftRawScore: z.number().min(0).max(1),
            rightRawScore: z.number().min(0).max(1),
            delta: z.number(),
          })
          .strict(),
      )
      .default([]),
    gradingEngineVersion: z.string().min(1).max(64),
  })
  .strict();

export const scoreExportArtifactSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCORE_EXPORT_ARTIFACT_SCHEMA_VERSION),
    exportId: z.string().min(1).max(64),
    scoreId: z.string().min(1).max(64),
    runId: runIdSchema,
    format: scoreExportFormatSchema,
    scenarioVersion: z.string().min(1).max(64),
    rubricVersion: z.string().min(1).max(64),
    gradingEngineVersion: z.string().min(1).max(64),
    integrityChecksum: z.string().min(1).max(128),
    contentChecksum: z.string().min(1).max(128),
    createdAt: utcTimestampSchema,
  })
  .strict();

export type ScoreErrorCode = z.infer<typeof scoreErrorCodeSchema>;
export type ScoreGradeBand = z.infer<typeof scoreGradeBandSchema>;
export type ScoreExplanationV1 = z.infer<typeof scoreExplanationSchema>;
export type ScoreRubricV1 = z.infer<typeof scoreRubricSchema>;
export type ScoreComponentV1 = z.infer<typeof scoreComponentSchema>;
export type ScoreProvenanceV1 = z.infer<typeof scoreProvenanceSchema>;
export type DecisionReviewV1 = z.infer<typeof decisionReviewSchema>;
export type MissedEvidenceItemV1 = z.infer<typeof missedEvidenceItemSchema>;
export type ValidAlternativeV1 = z.infer<typeof validAlternativeSchema>;
export type RunScoreV1 = z.infer<typeof runScoreSchema>;
export type AfterActionViewModelV1 = z.infer<typeof afterActionViewModelSchema>;
export type RunComparisonV1 = z.infer<typeof runComparisonSchema>;
export type ScoreExportArtifactV1 = z.infer<typeof scoreExportArtifactSchema>;
