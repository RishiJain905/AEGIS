import { z } from 'zod';

import { assetIdSchema, runIdSchema } from './primitives';
import { scenarioCommandTemplateSchema } from './proposals';
import {
  GHOST_BRANCH_REQUEST_SCHEMA_VERSION,
  GHOST_BRANCH_RESULT_SCHEMA_VERSION,
  GHOST_DECISION_POINT_SCHEMA_VERSION,
  GHOST_DECISION_POINTS_SCHEMA_VERSION,
} from './versioning';

// Ghost branch — post-run counterfactual replay contracts. Mirrors
// packages/contracts-python/src/aegis_contracts/ghost.py; keep the two in lockstep.

const MAX_SHIFT_SIM_SECONDS = 3600;

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

export const GhostDecisionKind = {
  EXECUTED_ACTION: 'executed_action',
  INACTION_WINDOW: 'inaction_window',
} as const;

export const ghostDecisionKindSchema = z.enum(['executed_action', 'inaction_window']);
export type GhostDecisionKindV1 = z.infer<typeof ghostDecisionKindSchema>;

export const GhostBranchMode = {
  SUBSTITUTE: 'substitute',
  DO_NOTHING: 'do_nothing',
  SHIFT: 'shift',
} as const;

export const ghostBranchModeSchema = z.enum(['substitute', 'do_nothing', 'shift']);
export type GhostBranchModeV1 = z.infer<typeof ghostBranchModeSchema>;

// One real decision the operator can fork from in the after-action ghost panel.
export const ghostDecisionPointSchema = z
  .object({
    schemaVersion: schemaVersionCheck(GHOST_DECISION_POINT_SCHEMA_VERSION),
    decisionRef: z.string().min(1).max(128),
    kind: ghostDecisionKindSchema,
    sequence: z.number().int().min(0),
    simTime: z.string(),
    scenarioCommand: scenarioCommandTemplateSchema.nullable().optional(),
    targetAssetId: z.string().nullable().optional(),
    actionClass: z.string().nullable().optional(),
    label: z.string(),
  })
  .strict();

export type GhostDecisionPointV1 = z.infer<typeof ghostDecisionPointSchema>;

export const ghostDecisionPointsSchema = z
  .object({
    schemaVersion: schemaVersionCheck(GHOST_DECISION_POINTS_SCHEMA_VERSION),
    runId: runIdSchema,
    decisionPoints: z.array(ghostDecisionPointSchema).default([]),
  })
  .strict();

export type GhostDecisionPointsV1 = z.infer<typeof ghostDecisionPointsSchema>;

// Ask the engine to re-simulate one decision differently (POST body).
export const ghostBranchRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(GHOST_BRANCH_REQUEST_SCHEMA_VERSION),
    decisionRef: z.string().min(1).max(128),
    mode: ghostBranchModeSchema,
    alternateCommand: scenarioCommandTemplateSchema.nullable().optional(),
    alternateTargetAssetId: assetIdSchema.nullable().optional(),
    shiftSimSeconds: z.number().int().nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.mode === 'substitute' && (value.alternateCommand ?? null) === null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'substitute mode requires alternateCommand',
        path: ['alternateCommand'],
      });
    }
    if (value.mode === 'shift') {
      const shift = value.shiftSimSeconds ?? 0;
      if (shift === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'shift mode requires a non-zero shiftSimSeconds',
          path: ['shiftSimSeconds'],
        });
      } else if (Math.abs(shift) > MAX_SHIFT_SIM_SECONDS) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `shiftSimSeconds exceeds +/-${String(MAX_SHIFT_SIM_SECONDS)}`,
          path: ['shiftSimSeconds'],
        });
      }
    }
  });

export type GhostBranchRequestV1 = z.infer<typeof ghostBranchRequestSchema>;

export const ghostTimelineBeatSchema = z
  .object({
    sequence: z.number().int().min(0),
    simTime: z.string(),
    kind: z.string(),
    label: z.string(),
    assetId: z.string().nullable().optional(),
    status: z.string().nullable().optional(),
  })
  .strict();

export type GhostTimelineBeatV1 = z.infer<typeof ghostTimelineBeatSchema>;

export const ghostAssetStatusSchema = z
  .object({
    assetId: z.string(),
    status: z.string(),
  })
  .strict();

export type GhostAssetStatusV1 = z.infer<typeof ghostAssetStatusSchema>;

export const ghostOutcomeSchema = z
  .object({
    label: z.string(),
    finalStatuses: z.array(ghostAssetStatusSchema).default([]),
    compromisedCount: z.number().int().min(0),
    containedCount: z.number().int().min(0),
    breachOccurred: z.boolean(),
    breachAssetIds: z.array(z.string()).default([]),
  })
  .strict();

export type GhostOutcomeV1 = z.infer<typeof ghostOutcomeSchema>;

export const ghostAssetDiffSchema = z
  .object({
    assetId: z.string(),
    realStatus: z.string(),
    ghostStatus: z.string(),
  })
  .strict();

export type GhostAssetDiffV1 = z.infer<typeof ghostAssetDiffSchema>;

// The counterfactual result (POST response) — real vs ghost, diffs, timeline, verdict.
export const ghostBranchResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(GHOST_BRANCH_RESULT_SCHEMA_VERSION),
    runId: runIdSchema,
    decisionRef: z.string(),
    mode: ghostBranchModeSchema,
    requestFingerprint: z.string(),
    resultHash: z.string(),
    divergenceSequence: z.number().int().min(0),
    divergenceSimTime: z.string(),
    stepsSimulated: z.number().int().min(0),
    realOutcome: ghostOutcomeSchema,
    ghostOutcome: ghostOutcomeSchema,
    assetDiffs: z.array(ghostAssetDiffSchema).default([]),
    ghostTimeline: z.array(ghostTimelineBeatSchema).default([]),
    realOverallScore: z.number().nullable().optional(),
    verdict: z.string(),
  })
  .strict();

export type GhostBranchResultV1 = z.infer<typeof ghostBranchResultSchema>;
