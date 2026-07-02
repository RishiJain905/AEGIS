import { z } from 'zod';

import { idempotencyMetadataSchema } from './api';
import { runSchema } from './entities';
import { graphDeltaSchema, graphSnapshotSchema } from './graph';
import { runIdSchema, sequenceSchema, simTimestampSchema } from './primitives';
import {
  CONNECTION_HEALTH_SCHEMA_VERSION,
  LIVE_RUN_SCHEMA_VERSION,
  REALTIME_REDUCER_ACTION_SCHEMA_VERSION,
  RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
  RUN_CREATE_REQUEST_SCHEMA_VERSION,
  SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION,
  TIMELINE_ENTRY_SCHEMA_VERSION,
} from './versioning';

export const ConnectionHealthState = {
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting',
  CATCHING_UP: 'catching_up',
  GAP: 'gap',
  SNAPSHOT_RESYNC: 'snapshot_resync',
  SIMULATOR_PAUSED: 'simulator_paused',
  LOCALLY_PAUSED: 'locally_paused',
  STALE: 'stale',
} as const;

export const connectionHealthStateSchema = z.enum([
  'connected',
  'disconnected',
  'reconnecting',
  'catching_up',
  'gap',
  'snapshot_resync',
  'simulator_paused',
  'locally_paused',
  'stale',
]);

export type ConnectionHealthStateValue =
  (typeof ConnectionHealthState)[keyof typeof ConnectionHealthState];

export const timelineEntrySchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    sequence: sequenceSchema,
    eventId: z.string().min(1),
    eventType: z.string().min(1),
    label: z.string().min(1),
    timestamp: simTimestampSchema,
    status: z.string().min(1),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== TIMELINE_ENTRY_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported timeline entry schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type TimelineEntryV1 = z.infer<typeof timelineEntrySchema>;

export const runReplicatedStateSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    lastAppliedSequence: sequenceSchema,
    runStatus: z.string().min(1),
    simTime: simTimestampSchema,
    graphRevision: z.number().int().min(0),
    timelineEntries: z.array(timelineEntrySchema),
    connectionHealth: connectionHealthStateSchema,
    isStale: z.boolean(),
    locallyPaused: z.boolean(),
    seenEventIds: z.array(z.string().min(1)).default([]),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== LIVE_RUN_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported live run schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type RunReplicatedState = z.infer<typeof runReplicatedStateSchema>;

export const realtimeReducerActionSchema = z.discriminatedUnion('type', [
  z
    .object({
      type: z.literal('apply_graph_delta'),
      delta: graphDeltaSchema,
    })
    .strict(),
  z
    .object({
      type: z.literal('load_graph_snapshot'),
      snapshot: graphSnapshotSchema,
    })
    .strict(),
  z
    .object({
      type: z.literal('append_timeline_entry'),
      entry: timelineEntrySchema,
    })
    .strict(),
  z
    .object({
      type: z.literal('update_run_status'),
      runStatus: z.string().min(1),
      simTime: simTimestampSchema,
      sequence: sequenceSchema,
    })
    .strict(),
  z
    .object({
      type: z.literal('set_connection_health'),
      connectionHealth: connectionHealthStateSchema,
      isStale: z.boolean().optional(),
    })
    .strict(),
  z
    .object({
      type: z.literal('mark_gap'),
      expectedSequence: sequenceSchema,
      receivedSequence: sequenceSchema,
    })
    .strict(),
  z
    .object({
      type: z.literal('noop_duplicate'),
      eventId: z.string().min(1),
      sequence: sequenceSchema,
    })
    .strict(),
  z
    .object({
      type: z.literal('set_locally_paused'),
      locallyPaused: z.boolean(),
    })
    .strict(),
  z
    .object({
      type: z.literal('advance_sequence'),
      sequence: sequenceSchema,
      eventId: z.string().min(1),
    })
    .strict(),
]);

export type RealtimeReducerAction = z.infer<typeof realtimeReducerActionSchema>;

export const snapshotBootstrapPayloadSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    run: runSchema,
    graphSnapshot: graphSnapshotSchema,
    lastAppliedSequence: sequenceSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported snapshot bootstrap schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type SnapshotBootstrapPayloadV1 = z.infer<typeof snapshotBootstrapPayloadSchema>;

export const runCreateRequestSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    scenarioPackagePath: z.string().min(1),
    seed: z.number().int(),
    runId: runIdSchema.optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== RUN_CREATE_REQUEST_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported run create request schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type RunCreateRequestV1 = z.infer<typeof runCreateRequestSchema>;

export const runCommandResponseSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    run: runSchema,
    eventsEmitted: z.number().int().min(0),
    idempotency: idempotencyMetadataSchema.optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== RUN_COMMAND_RESPONSE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported run command response schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type RunCommandResponseV1 = z.infer<typeof runCommandResponseSchema>;

export const connectionHealthSnapshotSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    connectionHealth: connectionHealthStateSchema,
    lastAppliedSequence: sequenceSchema,
    isStale: z.boolean(),
    locallyPaused: z.boolean(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== CONNECTION_HEALTH_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported connection health schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type ConnectionHealthSnapshotV1 = z.infer<typeof connectionHealthSnapshotSchema>;

export const REALTIME_REDUCER_ACTION_SCHEMA_VERSION_EXPORT = REALTIME_REDUCER_ACTION_SCHEMA_VERSION;
