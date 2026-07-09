/** Phase 26 replay frontend contracts. */

import { z } from 'zod';

import { incidentIdSchema, runIdSchema, sequenceSchema, utcTimestampSchema } from './primitives';
import {
  replayCursorSchema,
  replayErrorCodeSchema,
  replayProvenanceSchema,
  stateDiffSchema,
} from './replay';
import {
  HISTORICAL_GRAPH_ADAPTER_SCHEMA_VERSION,
  REPLAY_BOOKMARK_SCHEMA_VERSION,
  REPLAY_COMPARISON_SCHEMA_VERSION,
  REPLAY_VIEW_STATE_SCHEMA_VERSION,
  RETURN_TO_LIVE_RESULT_SCHEMA_VERSION,
  TIMELINE_FILTER_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const replayPlaybackSpeedSchema = z.enum(['0.5x', '1x', '2x', '4x']);

export const replayPlaybackStatusSchema = z.enum(['idle', 'playing', 'paused']);

export const replayLoadStatusSchema = z.enum(['idle', 'loading', 'ready', 'unavailable', 'error']);

export const replayBookmarkKindSchema = z.enum([
  'incident',
  'snapshot',
  'detection',
  'approval',
  'report',
  'custom',
]);

export const replayViewModeSchema = z.enum(['historical', 'playback']);

export const replayBookmarkSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_BOOKMARK_SCHEMA_VERSION),
    id: z.string().min(1).max(128),
    runId: runIdSchema,
    label: z.string().min(1).max(256),
    kind: replayBookmarkKindSchema,
    sequence: sequenceSchema,
    toSequence: sequenceSchema.nullable().optional(),
    incidentId: incidentIdSchema.nullable().optional(),
    description: z.string().max(512).nullable().optional(),
  })
  .strict();

export const timelineFilterSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TIMELINE_FILTER_SCHEMA_VERSION),
    runId: runIdSchema,
    eventTypes: z.array(z.string().min(1).max(128)).default([]),
    incidentId: incidentIdSchema.nullable().optional(),
    query: z.string().max(256).nullable().optional(),
    fromSequence: sequenceSchema.nullable().optional(),
    toSequence: sequenceSchema.nullable().optional(),
    includeBookmarksOnly: z.boolean().default(false),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (
      value.fromSequence != null &&
      value.toSequence != null &&
      value.toSequence < value.fromSequence
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'toSequence must be >= fromSequence',
      });
    }
  });

export const historicalGraphAdapterSchema = z
  .object({
    schemaVersion: schemaVersionCheck(HISTORICAL_GRAPH_ADAPTER_SCHEMA_VERSION),
    runId: runIdSchema,
    sequence: sequenceSchema,
    graphRevision: z.number().int().min(0),
    stateDigest: z.string().min(1).max(128),
    source: z.literal('replay_state_graph'),
    readOnly: z.literal(true),
  })
  .strict();

export const replayComparisonSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_COMPARISON_SCHEMA_VERSION),
    runId: runIdSchema,
    leftSequence: sequenceSchema,
    rightSequence: sequenceSchema,
    leftLabel: z.string().min(1).max(128).nullable().optional(),
    rightLabel: z.string().min(1).max(128).nullable().optional(),
    diff: stateDiffSchema.nullable().optional(),
    loading: z.boolean().default(false),
    errorCode: replayErrorCodeSchema.nullable().optional(),
    errorMessage: z.string().max(512).nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.rightSequence < value.leftSequence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'rightSequence must be >= leftSequence',
      });
    }
  });

export const returnToLiveResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RETURN_TO_LIVE_RESULT_SCHEMA_VERSION),
    runId: runIdSchema,
    fromSequence: sequenceSchema,
    liveRoute: z.string().min(1).max(512),
    authoritativeResyncRequired: z.literal(true),
    replayStoreCleared: z.boolean(),
    completedAt: utcTimestampSchema,
  })
  .strict();

export const replayViewStateSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_VIEW_STATE_SCHEMA_VERSION),
    runId: runIdSchema,
    mode: replayViewModeSchema,
    cursor: replayCursorSchema,
    minSequence: sequenceSchema,
    maxSequence: sequenceSchema,
    playbackStatus: replayPlaybackStatusSchema,
    speed: replayPlaybackSpeedSchema,
    loadStatus: replayLoadStatusSchema,
    reducedMotion: z.boolean().default(false),
    selectedBookmarkId: z.string().min(1).max(128).nullable().optional(),
    timelineFilter: timelineFilterSchema.nullable().optional(),
    comparison: replayComparisonSchema.nullable().optional(),
    historicalGraph: historicalGraphAdapterSchema.nullable().optional(),
    provenance: replayProvenanceSchema.nullable().optional(),
    stateDigest: z.string().min(1).max(128).nullable().optional(),
    errorCode: replayErrorCodeSchema.nullable().optional(),
    errorMessage: z.string().max(512).nullable().optional(),
    lastReconstructedAt: utcTimestampSchema.nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.maxSequence < value.minSequence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'maxSequence must be >= minSequence',
      });
    }
    if (value.cursor.sequence < value.minSequence || value.cursor.sequence > value.maxSequence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'cursor.sequence must be within minSequence..maxSequence',
      });
    }
  });

export type ReplayPlaybackSpeed = z.infer<typeof replayPlaybackSpeedSchema>;
export type ReplayPlaybackStatus = z.infer<typeof replayPlaybackStatusSchema>;
export type ReplayLoadStatus = z.infer<typeof replayLoadStatusSchema>;
export type ReplayBookmarkKind = z.infer<typeof replayBookmarkKindSchema>;
export type ReplayViewMode = z.infer<typeof replayViewModeSchema>;
export type ReplayBookmarkV1 = z.infer<typeof replayBookmarkSchema>;
export type TimelineFilterV1 = z.infer<typeof timelineFilterSchema>;
export type HistoricalGraphAdapterV1 = z.infer<typeof historicalGraphAdapterSchema>;
export type ReplayComparisonV1 = z.infer<typeof replayComparisonSchema>;
export type ReturnToLiveResultV1 = z.infer<typeof returnToLiveResultSchema>;
export type ReplayViewStateV1 = z.infer<typeof replayViewStateSchema>;
