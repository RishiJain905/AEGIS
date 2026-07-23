import { z } from 'zod';

import { rulesOfEngagementSchema } from './entities';
import { policyOutcomeSchema, scenarioCommandTemplateSchema } from './proposals';
import { assetIdSchema, runIdSchema, utcTimestampSchema } from './primitives';
import {
  CONSOLE_ASSET_DETAIL_SCHEMA_VERSION,
  CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
  CONSOLE_EVENT_SEARCH_RESULT_SCHEMA_VERSION,
  CREATE_DIRECTIVE_REQUEST_SCHEMA_VERSION,
  OPERATOR_ACTION_REQUEST_SCHEMA_VERSION,
  OPERATOR_ACTION_RESPONSE_SCHEMA_VERSION,
  OPERATOR_HYPOTHESIS_REQUEST_SCHEMA_VERSION,
  ROE_CHANGE_REQUEST_SCHEMA_VERSION,
  RUN_FEED_ENTRY_SCHEMA_VERSION,
  RUN_FEED_PAGE_SCHEMA_VERSION,
  STANDING_DIRECTIVE_SCHEMA_VERSION,
} from './versioning';

const MAX_REASON_LENGTH = 2048;
const MAX_DIRECTIVE_LENGTH = 2048;

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

export const OperatorActionStatus = {
  EXECUTED: 'executed',
  CONFIRMATION_REQUIRED: 'confirmation_required',
  BLOCKED: 'blocked',
} as const;

export const operatorActionStatusSchema = z.enum(['executed', 'confirmation_required', 'blocked']);

export type OperatorActionStatusV1 = z.infer<typeof operatorActionStatusSchema>;

// Player-initiated containment. Flows through the policy engine exactly like an agent
// proposal; Class 2/3 require `confirm` (operator is the incident commander).
export const operatorActionRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(OPERATOR_ACTION_REQUEST_SCHEMA_VERSION),
    scenarioCommand: scenarioCommandTemplateSchema,
    targetAssetId: assetIdSchema,
    reason: z.string().min(1).max(MAX_REASON_LENGTH),
    confirm: z.boolean().default(false),
    incidentId: z.string().nullable().optional(),
    idempotencyKey: z.string().min(1).max(256),
  })
  .strict();

export type OperatorActionRequestV1 = z.infer<typeof operatorActionRequestSchema>;

export const operatorActionResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(OPERATOR_ACTION_RESPONSE_SCHEMA_VERSION),
    proposalId: z.string().min(1),
    incidentId: z.string().min(1),
    actionClass: actionClassSchema,
    status: operatorActionStatusSchema,
    policyOutcome: policyOutcomeSchema,
    reasonCodes: z.array(z.string()).default([]),
    executed: z.boolean().default(false),
    executedActionId: z.string().nullable().optional(),
    approvalId: z.string().nullable().optional(),
  })
  .strict();

export type OperatorActionResponseV1 = z.infer<typeof operatorActionResponseSchema>;

export const roeChangeRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ROE_CHANGE_REQUEST_SCHEMA_VERSION),
    roe: rulesOfEngagementSchema,
  })
  .strict();

export type RoeChangeRequestV1 = z.infer<typeof roeChangeRequestSchema>;

// A persistent operator tasking re-evaluated when new matching evidence lands.
export const standingDirectiveSchema = z
  .object({
    schemaVersion: schemaVersionCheck(STANDING_DIRECTIVE_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    runId: runIdSchema,
    text: z.string().min(1).max(MAX_DIRECTIVE_LENGTH),
    scopeAssetIds: z.array(assetIdSchema).default([]),
    scopeZoneIds: z.array(z.string()).default([]),
    active: z.boolean().default(true),
    createdBy: z.string().min(1),
    createdAt: utcTimestampSchema,
  })
  .strict();

export type StandingDirectiveV1 = z.infer<typeof standingDirectiveSchema>;

export const createDirectiveRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CREATE_DIRECTIVE_REQUEST_SCHEMA_VERSION),
    text: z.string().min(1).max(MAX_DIRECTIVE_LENGTH),
    scopeAssetIds: z.array(assetIdSchema).default([]),
    scopeZoneIds: z.array(z.string()).default([]),
  })
  .strict();

export type CreateDirectiveRequestV1 = z.infer<typeof createDirectiveRequestSchema>;

// Operator log/event search — the player's read peer to the agents' search_events.
export const consoleEventSearchRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION),
    assetId: assetIdSchema.nullable().optional(),
    eventTypePrefix: z.string().max(128).nullable().optional(),
    text: z.string().max(256).nullable().optional(),
    fromSimTime: utcTimestampSchema.nullable().optional(),
    toSimTime: utcTimestampSchema.nullable().optional(),
    cursor: z.number().int().min(0).nullable().optional(),
    limit: z.number().int().min(1).max(500).default(100),
  })
  .strict();

export type ConsoleEventSearchRequestV1 = z.infer<typeof consoleEventSearchRequestSchema>;

export const consoleEventSchema = z
  .object({
    eventId: z.string().min(1),
    sequence: z.number().int(),
    type: z.string(),
    simTime: z.string(),
    assetId: z.string().nullable().optional(),
    payload: z.record(z.unknown()).default({}),
  })
  .strict();

export type ConsoleEventV1 = z.infer<typeof consoleEventSchema>;

export const consoleEventSearchResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CONSOLE_EVENT_SEARCH_RESULT_SCHEMA_VERSION),
    events: z.array(consoleEventSchema).default([]),
    count: z.number().int().default(0),
    nextCursor: z.number().int().nullable().optional(),
  })
  .strict();

export type ConsoleEventSearchResultV1 = z.infer<typeof consoleEventSearchResultSchema>;

// A single graph relationship touching the asset in the console deep-dive.
export const consoleAssetRelationshipSchema = z
  .object({
    edgeId: z.string().min(1),
    relationshipType: z.string().min(1),
    sourceAssetId: assetIdSchema,
    targetAssetId: assetIdSchema,
    direction: z.string(),
  })
  .strict();

export type ConsoleAssetRelationshipV1 = z.infer<typeof consoleAssetRelationshipSchema>;

// Operator asset deep-dive: current graph node, its relationships and recent events.
export const consoleAssetDetailSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CONSOLE_ASSET_DETAIL_SCHEMA_VERSION),
    assetId: assetIdSchema,
    entityType: z.string().min(1),
    assetType: z.string().nullable().optional(),
    label: z.string(),
    status: z.string(),
    riskScore: z.number().nullable().optional(),
    criticality: z.number().nullable().optional(),
    clusterId: z.string().nullable().optional(),
    relationships: z.array(consoleAssetRelationshipSchema).default([]),
    recentEvents: z.array(consoleEventSchema).default([]),
  })
  .strict();

export type ConsoleAssetDetailV1 = z.infer<typeof consoleAssetDetailSchema>;

// Create an operator-pinned hypothesis, stored alongside agent hypotheses.
export const operatorHypothesisRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(OPERATOR_HYPOTHESIS_REQUEST_SCHEMA_VERSION),
    statement: z.string().min(1).max(2048),
    assetIds: z.array(assetIdSchema).default([]),
    confidence: z.number().min(0).max(1).default(0.5),
    incidentId: z.string().nullable().optional(),
  })
  .strict();

export type OperatorHypothesisRequestV1 = z.infer<typeof operatorHypothesisRequestSchema>;

// A single entry in the unified ops feed — a thin projection over the events table.
export const runFeedEntrySchema = z
  .object({
    schemaVersion: schemaVersionCheck(RUN_FEED_ENTRY_SCHEMA_VERSION),
    sequence: z.number().int(),
    eventId: z.string().min(1),
    type: z.string().min(1),
    category: z.string().min(1),
    simTime: z.string(),
    initiator: z.string().nullable().optional(),
    summary: z.string(),
    payload: z.record(z.unknown()).default({}),
  })
  .strict();

export type RunFeedEntryV1 = z.infer<typeof runFeedEntrySchema>;

export const runFeedPageSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RUN_FEED_PAGE_SCHEMA_VERSION),
    entries: z.array(runFeedEntrySchema).default([]),
    nextCursor: z.number().int().nullable().optional(),
  })
  .strict();

export type RunFeedPageV1 = z.infer<typeof runFeedPageSchema>;
