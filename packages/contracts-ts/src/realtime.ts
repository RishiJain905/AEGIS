import { z } from 'zod';

import { domainEventEnvelopeSchema } from './events';
import { eventIdSchema, runIdSchema, sequenceSchema, utcTimestampSchema } from './primitives';
import {
  BACKFILL_REQUEST_SCHEMA_VERSION,
  BACKFILL_RESULT_SCHEMA_VERSION,
  CONSUMER_CURSOR_SCHEMA_VERSION,
  DEAD_LETTER_RECORD_SCHEMA_VERSION,
  REALTIME_MESSAGE_SCHEMA_VERSION,
} from './versioning';

export const streamingErrorCodeSchema = z.enum([
  'STREAM_GAP_DETECTED',
  'STREAM_DUPLICATE',
  'STREAM_PUBLISH_FAILED',
  'STREAM_CONSUMER_UNAVAILABLE',
  'STREAM_POISON_MESSAGE',
  'STREAM_BACKFILL_FAILED',
]);

export const realtimeMessageEnvelopeSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    channel: z.string().min(1).max(128),
    streamMessageId: z.string().nullable().optional(),
    publishedAt: utcTimestampSchema,
    event: domainEventEnvelopeSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== REALTIME_MESSAGE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported realtime message schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const consumerCursorSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    consumerGroup: z.string().min(1).max(128),
    consumerName: z.string().min(1).max(128),
    streamKey: z.string().min(1).max(256),
    lastEventId: eventIdSchema,
    lastRunId: runIdSchema,
    lastSequence: sequenceSchema,
    updatedAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== CONSUMER_CURSOR_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported consumer cursor schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const deadLetterRecordSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    eventId: eventIdSchema,
    runId: runIdSchema,
    sequence: sequenceSchema,
    consumerId: z.string().min(1).max(256),
    streamKey: z.string().min(1).max(256),
    streamMessageId: z.string().min(1).max(128),
    errorCode: z.string().min(1).max(128),
    errorMessage: z.string().min(1).max(2048),
    attemptCount: z.number().int().min(1),
    originalEnvelope: z.record(z.string(), z.unknown()),
    createdAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== DEAD_LETTER_RECORD_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported dead letter record schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const backfillRequestSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema.nullable().optional(),
    fromSequence: z.number().int().min(0).nullable().optional(),
    toSequence: z.number().int().min(0).nullable().optional(),
    streamKey: z.string().max(256).nullable().optional(),
    force: z.boolean().default(false),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== BACKFILL_REQUEST_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported backfill request schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const backfillResultSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema.nullable().optional(),
    eventsScanned: z.number().int().min(0),
    eventsPublished: z.number().int().min(0),
    eventsSkipped: z.number().int().min(0),
    completedAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== BACKFILL_RESULT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported backfill result schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type StreamingErrorCode = z.infer<typeof streamingErrorCodeSchema>;
export type RealtimeMessageEnvelopeV1 = z.infer<typeof realtimeMessageEnvelopeSchema>;
export type ConsumerCursorV1 = z.infer<typeof consumerCursorSchema>;
export type DeadLetterRecordV1 = z.infer<typeof deadLetterRecordSchema>;
export type BackfillRequestV1 = z.infer<typeof backfillRequestSchema>;
export type BackfillResultV1 = z.infer<typeof backfillResultSchema>;
