import { z } from 'zod';

import { idempotencyMetadataSchema } from './api';
import { runLoadoutSchema, runSchema } from './entities';
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
    // Fog-of-war ambient pressure scalar in [0, 1]; null when absent/not yet computed.
    // Additive (schemaVersion unchanged). Scalar only — no asset/condition leak.
    threatTempo: z.number().min(0).max(1).nullable().optional(),
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
    // Optional: omit to have the API draw a cryptographically random seed and
    // persist it (server-side RNG). A supplied seed pins the run deterministically.
    seed: z.number().int().optional(),
    runId: runIdSchema.optional(),
    // Phase 7 capability loadout chosen at launch. Additive optional field
    // (schemaVersion stays 1): when omitted the server persists the default loadout.
    loadout: runLoadoutSchema.nullable().optional(),
    // Optional one-line commander's intent (untrusted, non-authoritative operator free
    // text). Bounded to a single directive line. Additive optional field (schemaVersion
    // stays 1); persisted on the run.
    commanderIntent: z.string().max(280).nullable().optional(),
    // Reset-and-replay for pinned-seed scenarios. Run ids are derived from
    // (seed, scenarioVersionId), so a pinned seed resolves to exactly one run id for the
    // lifetime of a database: relaunching returns the run created the first time, which by
    // then is finished. When set the server destroys that run (owner-or-admin only) and
    // creates it again from scratch. Additive optional field (schemaVersion stays 1);
    // omitted keeps the resume behaviour.
    restartExisting: z.boolean().optional(),
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
