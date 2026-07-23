/**
 * Operator skill-telemetry profile contracts (mirror of aegis_contracts.operator_profile).
 *
 * A cross-run, read-only aggregation of the operator's own habits, computed on demand from
 * persisted run data. All metrics and coaching lines are deterministic heuristics and
 * non-authoritative. See the Python module for the canonical field docs.
 */

import { z } from 'zod';

import { OPERATOR_PROFILE_SCHEMA_VERSION } from './versioning';

export const coachingToneSchema = z.enum(['reinforce', 'improve', 'neutral']);
export type CoachingTone = z.infer<typeof coachingToneSchema>;

export const operatorRunSummarySchema = z
  .object({
    runId: z.string().min(1),
    scenarioId: z.string(),
    seed: z.number().int(),
    status: z.string(),
    startedAt: z.string(),
    score: z.number().min(0).max(1).nullable().optional(),
    timeToFirstTriage: z.number().min(0).nullable().optional(),
    containmentLatency: z.number().min(0).nullable().optional(),
    firstAgentRole: z.string().nullable().optional(),
    aggressiveActionCount: z.number().int().min(0),
    overContainmentCount: z.number().int().min(0).nullable().optional(),
    hypothesisCount: z.number().int().min(0),
    falseHypothesisCount: z.number().int().min(0),
  })
  .strict();
export type OperatorRunSummaryV1 = z.infer<typeof operatorRunSummarySchema>;

export const operatorProfileMetricsSchema = z
  .object({
    runsAnalyzed: z.number().int().min(0),
    avgTimeToFirstTriage: z.number().min(0).nullable().optional(),
    avgContainmentLatency: z.number().min(0).nullable().optional(),
    overContainmentRatio: z.number().min(0).max(1).nullable().optional(),
    falseHypothesisRate: z.number().min(0).max(1).nullable().optional(),
    avgScore: z.number().min(0).max(1).nullable().optional(),
    scoreTrend: z.array(z.number()),
  })
  .strict();
export type OperatorProfileMetricsV1 = z.infer<typeof operatorProfileMetricsSchema>;

export const coachingLineSchema = z
  .object({
    id: z.string().min(1),
    tone: coachingToneSchema,
    message: z.string().min(1).max(400),
  })
  .strict();
export type CoachingLineV1 = z.infer<typeof coachingLineSchema>;

export const operatorProfileSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    ownerUserId: z.string().min(1),
    generatedAt: z.string(),
    metrics: operatorProfileMetricsSchema,
    runs: z.array(operatorRunSummarySchema),
    coaching: z.array(coachingLineSchema),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== OPERATOR_PROFILE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported operator profile schema version: ${String(value.schemaVersion)}`,
      });
    }
  });
export type OperatorProfileV1 = z.infer<typeof operatorProfileSchema>;
