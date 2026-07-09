/** Phase 25 snapshot and replay engine contracts. */

import { z } from "zod";

import {
  actionProposalSchema,
  agentSessionSchema,
  approvalSchema,
  evidenceSchema,
  executedActionSchema,
  incidentSchema,
  runSchema,
} from "./entities";
import { graphSnapshotSchema } from "./graph";
import {
  eventIdSchema,
  incidentIdSchema,
  replaySnapshotIdSchema,
  runIdSchema,
  sequenceSchema,
  simTimestampSchema,
  utcTimestampSchema,
} from "./primitives";
import {
  REPLAY_CURSOR_RANGE_SCHEMA_VERSION,
  REPLAY_CURSOR_SCHEMA_VERSION,
  REPLAY_EQUIVALENCE_RESULT_SCHEMA_VERSION,
  REPLAY_PROVENANCE_SCHEMA_VERSION,
  REPLAY_SNAPSHOT_SCHEMA_VERSION,
  REPLAY_STATE_SCHEMA_VERSION,
  SNAPSHOT_MANIFEST_SCHEMA_VERSION,
  STATE_DIFF_SCHEMA_VERSION,
} from "./versioning";

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const snapshotTriggerReasonSchema = z.enum([
  "sequence_interval",
  "run_paused",
  "run_completed",
  "explicit_request",
  "worker_backfill",
]);

export const snapshotCompressionSchema = z.enum(["none", "gzip"]);

export const replayModeSchema = z.enum([
  "from_events",
  "from_snapshot_plus_events",
]);

export const replayErrorCodeSchema = z.enum([
  "SNAPSHOT_CHECKSUM_MISMATCH",
  "SNAPSHOT_INCOMPATIBLE",
  "SNAPSHOT_MISSING",
  "REPLAY_SEQUENCE_GAP",
  "REPLAY_DUPLICATE_EVENT",
  "REPLAY_LIVE_MUTATION_FORBIDDEN",
  "REPLAY_VALIDATION_FAILED",
  "REPLAY_NOT_FOUND",
]);

export const replayRiskScoreSchema = z
  .object({
    assetId: z.string().min(1).max(128),
    score: z.number().min(0).max(1),
    revision: z.number().int().min(0),
  })
  .strict();

export const replayReportRefSchema = z
  .object({
    reportId: z.string().min(1).max(64),
    reportVersionId: z.string().min(1).max(64),
    incidentId: incidentIdSchema.nullable().optional(),
    status: z.string().min(1).max(64),
    checksum: z.string().min(1).max(128).nullable().optional(),
  })
  .strict();

export const replayAgentArtifactRefSchema = z
  .object({
    artifactId: z.string().min(1).max(64),
    agentSessionId: z.string().min(1).max(128),
    artifactType: z.string().min(1).max(64),
    objectKey: z.string().min(1).max(1024).nullable().optional(),
    checksum: z.string().min(1).max(128).nullable().optional(),
  })
  .strict();

export const replayAuditEventRefSchema = z
  .object({
    eventId: eventIdSchema,
    sequence: sequenceSchema,
    eventType: z.string().min(1).max(128),
    summary: z.string().min(1).max(512),
  })
  .strict();

export const replayCursorSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_CURSOR_SCHEMA_VERSION),
    runId: runIdSchema,
    sequence: sequenceSchema,
    simTime: simTimestampSchema.nullable().optional(),
    incidentId: incidentIdSchema.nullable().optional(),
  })
  .strict();

export const replayCursorRangeSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_CURSOR_RANGE_SCHEMA_VERSION),
    runId: runIdSchema,
    fromSequence: sequenceSchema,
    toSequence: sequenceSchema,
    incidentId: incidentIdSchema.nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.toSequence < value.fromSequence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "toSequence must be >= fromSequence",
      });
    }
  });

export const replayProvenanceSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_PROVENANCE_SCHEMA_VERSION),
    runId: runIdSchema,
    mode: replayModeSchema,
    snapshotId: replaySnapshotIdSchema.nullable().optional(),
    snapshotSequence: sequenceSchema.nullable().optional(),
    appliedFromSequence: sequenceSchema,
    appliedToSequence: sequenceSchema,
    appliedEventCount: z.number().int().min(0),
    fallbackReason: z.string().max(512).nullable().optional(),
    reconstructedAt: utcTimestampSchema,
  })
  .strict();

export const replayStateSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_STATE_SCHEMA_VERSION),
    runId: runIdSchema,
    cursor: replayCursorSchema,
    run: runSchema.nullable().optional(),
    graph: graphSnapshotSchema.nullable().optional(),
    incidents: z.array(incidentSchema).default([]),
    evidence: z.array(evidenceSchema).default([]),
    riskScores: z.array(replayRiskScoreSchema).default([]),
    agentSessions: z.array(agentSessionSchema).default([]),
    agentArtifacts: z.array(replayAgentArtifactRefSchema).default([]),
    proposals: z.array(actionProposalSchema).default([]),
    approvals: z.array(approvalSchema).default([]),
    executedActions: z.array(executedActionSchema).default([]),
    reports: z.array(replayReportRefSchema).default([]),
    auditEvents: z.array(replayAuditEventRefSchema).default([]),
    stateDigest: z.string().min(1).max(128),
    provenance: replayProvenanceSchema,
  })
  .strict();

export const replaySnapshotSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_SNAPSHOT_SCHEMA_VERSION),
    id: replaySnapshotIdSchema,
    runId: runIdSchema,
    sequence: sequenceSchema,
    simTime: simTimestampSchema,
    scenarioVersionId: z.string().min(1).max(128),
    engineVersion: z.string().min(1).max(64),
    projectorVersion: z.string().min(1).max(64),
    workspaceVersion: z.string().min(1).max(64),
    eventRangeFrom: sequenceSchema,
    eventRangeTo: sequenceSchema,
    state: replayStateSchema,
    stateDigest: z.string().min(1).max(128),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const snapshotManifestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SNAPSHOT_MANIFEST_SCHEMA_VERSION),
    snapshotId: replaySnapshotIdSchema,
    runId: runIdSchema,
    sequence: sequenceSchema,
    simTime: simTimestampSchema,
    scenarioVersionId: z.string().min(1).max(128),
    engineVersion: z.string().min(1).max(64),
    projectorVersion: z.string().min(1).max(64),
    workspaceVersion: z.string().min(1).max(64),
    eventRangeFrom: sequenceSchema,
    eventRangeTo: sequenceSchema,
    checksum: z.string().min(1).max(128),
    compression: snapshotCompressionSchema,
    contentType: z.string().min(1).max(256),
    sizeBytes: z.number().int().min(0),
    objectKey: z.string().min(1).max(1024),
    stateDigest: z.string().min(1).max(128),
    triggerReason: snapshotTriggerReasonSchema,
    retentionClass: z.string().min(1).max(64),
    createdAt: utcTimestampSchema,
    compatible: z.boolean().default(true),
  })
  .strict();

export const stateDiffEntrySchema = z
  .object({
    path: z.string().min(1).max(512),
    changeType: z.string().min(1).max(32),
    before: z.unknown().nullable().optional(),
    after: z.unknown().nullable().optional(),
  })
  .strict();

export const stateDiffSchema = z
  .object({
    schemaVersion: schemaVersionCheck(STATE_DIFF_SCHEMA_VERSION),
    runId: runIdSchema,
    fromCursor: replayCursorSchema,
    toCursor: replayCursorSchema,
    entries: z.array(stateDiffEntrySchema).default([]),
    fromDigest: z.string().min(1).max(128),
    toDigest: z.string().min(1).max(128),
    equivalent: z.boolean(),
  })
  .strict();

export const replayEquivalenceResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPLAY_EQUIVALENCE_RESULT_SCHEMA_VERSION),
    runId: runIdSchema,
    sequence: sequenceSchema,
    liveDigest: z.string().min(1).max(128),
    reconstructedDigest: z.string().min(1).max(128),
    equivalent: z.boolean(),
    diff: stateDiffSchema.nullable().optional(),
    provenance: replayProvenanceSchema,
    checkedAt: utcTimestampSchema,
  })
  .strict();
