/** Phase 31 observability contracts — telemetry context, logs, health, metrics policy. */

import { z } from 'zod';

import {
  agentSessionIdSchema,
  correlationIdSchema,
  incidentIdSchema,
  runIdSchema,
  sequenceSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  DEPENDENCY_STATUS_SCHEMA_VERSION,
  HEALTH_RESPONSE_SCHEMA_VERSION,
  METRIC_LABEL_POLICY_SCHEMA_VERSION,
  READY_RESPONSE_SCHEMA_VERSION,
  STRUCTURED_LOG_RECORD_SCHEMA_VERSION,
  TELEMETRY_CONTEXT_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const healthStatusSchema = z.enum(['ok', 'degraded', 'failed']);
export const readyStatusSchema = z.enum(['ready', 'not_ready', 'degraded']);
export const dependencyStateSchema = z.enum(['ok', 'degraded', 'unavailable', 'failed', 'skipped']);
export const logOutcomeSchema = z.enum(['success', 'failure', 'timeout', 'cancelled', 'rejected']);
export const actorKindSchema = z.enum(['user', 'service', 'system', 'agent', 'anonymous']);
export const metricTypeSchema = z.enum(['counter', 'histogram', 'gauge', 'up_down_counter']);

export const ALLOWED_METRIC_LABELS = [
  'service',
  'operation',
  'status',
  'outcome',
  'provider',
  'model_alias',
  'agent_name',
  'dependency',
  'method',
  'route_group',
  'error_kind',
  'ws_event',
] as const;

export const FORBIDDEN_METRIC_LABELS = [
  'user_id',
  'userId',
  'event_id',
  'eventId',
  'request_id',
  'requestId',
  'trace_id',
  'traceId',
  'run_id',
  'runId',
  'incident_id',
  'incidentId',
  'prompt',
  'url',
  'error_message',
  'errorMessage',
  'session_id',
  'sessionId',
  'actor_id',
  'actorId',
] as const;

export const telemetryContextSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TELEMETRY_CONTEXT_SCHEMA_VERSION),
    traceId: traceIdSchema,
    spanId: z.string().max(32).nullable().optional(),
    correlationId: correlationIdSchema.nullable().optional(),
    requestId: z.string().max(128).nullable().optional(),
    runId: runIdSchema.nullable().optional(),
    incidentId: incidentIdSchema.nullable().optional(),
    agentSessionId: agentSessionIdSchema.nullable().optional(),
    eventSequence: sequenceSchema.nullable().optional(),
    service: z.string().min(1).max(64),
    operation: z.string().min(1).max(128),
    actorId: z.string().max(128).nullable().optional(),
    actorKind: actorKindSchema.nullable().optional(),
    actorRole: z.string().max(64).nullable().optional(),
    outcome: logOutcomeSchema.nullable().optional(),
    durationMs: z.number().min(0).nullable().optional(),
    baggage: z.record(z.string(), z.string()).default({}),
  })
  .strict();

export const structuredLogRecordSchema = z
  .object({
    schemaVersion: schemaVersionCheck(STRUCTURED_LOG_RECORD_SCHEMA_VERSION),
    timestamp: utcTimestampSchema,
    level: z.string().min(1).max(16),
    message: z.string().min(1).max(4096),
    traceId: traceIdSchema.nullable().optional(),
    spanId: z.string().max(32).nullable().optional(),
    correlationId: correlationIdSchema.nullable().optional(),
    requestId: z.string().max(128).nullable().optional(),
    runId: runIdSchema.nullable().optional(),
    incidentId: incidentIdSchema.nullable().optional(),
    agentSessionId: agentSessionIdSchema.nullable().optional(),
    eventSequence: sequenceSchema.nullable().optional(),
    service: z.string().min(1).max(64),
    operation: z.string().min(1).max(128),
    actorId: z.string().max(128).nullable().optional(),
    actorKind: actorKindSchema.nullable().optional(),
    outcome: logOutcomeSchema.nullable().optional(),
    durationMs: z.number().min(0).nullable().optional(),
    errorKind: z.string().max(128).nullable().optional(),
    attributes: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const dependencyStatusSchema = z
  .object({
    schemaVersion: schemaVersionCheck(DEPENDENCY_STATUS_SCHEMA_VERSION),
    name: z.string().min(1).max(64),
    state: dependencyStateSchema,
    required: z.boolean().default(true),
    latencyMs: z.number().min(0).nullable().optional(),
    message: z.string().max(512).nullable().optional(),
    checkedAt: utcTimestampSchema.nullable().optional(),
  })
  .strict();

export const healthResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(HEALTH_RESPONSE_SCHEMA_VERSION),
    status: healthStatusSchema,
    service: z.string().min(1).max(64),
    version: z.string().min(1).max(64),
    checkedAt: utcTimestampSchema.nullable().optional(),
  })
  .strict();

export const readyResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(READY_RESPONSE_SCHEMA_VERSION),
    status: readyStatusSchema,
    service: z.string().min(1).max(64),
    environment: z.string().min(1).max(32),
    dependencies: z.array(dependencyStatusSchema).default([]),
    checkedAt: utcTimestampSchema.nullable().optional(),
  })
  .strict();

export const metricLabelPolicySchema = z
  .object({
    schemaVersion: schemaVersionCheck(METRIC_LABEL_POLICY_SCHEMA_VERSION),
    metricName: z.string().min(1).max(128),
    metricType: metricTypeSchema,
    unit: z.string().min(1).max(32),
    description: z.string().min(1).max(512),
    allowedLabels: z.array(z.string()).default([]),
    source: z.string().min(1).max(128),
  })
  .strict()
  .superRefine((value, ctx) => {
    for (const label of value.allowedLabels) {
      if ((FORBIDDEN_METRIC_LABELS as readonly string[]).includes(label)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Forbidden high-cardinality metric label: ${label}`,
          path: ['allowedLabels'],
        });
      } else if (!(ALLOWED_METRIC_LABELS as readonly string[]).includes(label)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Metric label not in allowlist: ${label}`,
          path: ['allowedLabels'],
        });
      }
    }
  });

export type TelemetryContextV1 = z.infer<typeof telemetryContextSchema>;
export type StructuredLogRecordV1 = z.infer<typeof structuredLogRecordSchema>;
export type DependencyStatusV1 = z.infer<typeof dependencyStatusSchema>;
export type HealthResponseV1 = z.infer<typeof healthResponseSchema>;
export type ReadyResponseV1 = z.infer<typeof readyResponseSchema>;
export type MetricLabelPolicyV1 = z.infer<typeof metricLabelPolicySchema>;
export type HealthStatusV1 = z.infer<typeof healthStatusSchema>;
export type ReadyStatusV1 = z.infer<typeof readyStatusSchema>;
export type DependencyStateV1 = z.infer<typeof dependencyStateSchema>;
export type LogOutcomeV1 = z.infer<typeof logOutcomeSchema>;
export type ActorKindV1 = z.infer<typeof actorKindSchema>;
export type MetricTypeV1 = z.infer<typeof metricTypeSchema>;
