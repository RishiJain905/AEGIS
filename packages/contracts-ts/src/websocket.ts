import { z } from 'zod';

import { apiErrorEnvelopeSchema } from './errors';
import { runIdSchema, sequenceSchema, traceIdSchema, utcTimestampSchema } from './primitives';
import { realtimeMessageEnvelopeSchema } from './realtime';
import { PROTOCOL_VERSION_V1, WEBSOCKET_FRAME_SCHEMA_VERSION } from './versioning';

export const websocketMessageTypeSchema = z.enum([
  'hello',
  'hello_ack',
  'subscribe',
  'unsubscribe',
  'pong',
  'subscribed',
  'event',
  'warning',
  'error',
  'snapshot_required',
  'ping',
  'resync_complete',
]);

export const websocketErrorCodeSchema = z.enum([
  'WS_UNAUTHORIZED',
  'WS_FORBIDDEN',
  'WS_INVALID_MESSAGE',
  'WS_MESSAGE_TOO_LARGE',
  'WS_UNSUPPORTED_PROTOCOL',
  'WS_UNKNOWN_RUN',
  'WS_SEQUENCE_GAP',
  'WS_QUEUE_OVERFLOW',
  'WS_IDLE_TIMEOUT',
  'WS_CONNECTION_LIMIT',
]);

export const websocketDeliveryModeSchema = z.enum(['stream', 'backfill', 'snapshot_required']);

export const websocketHelloPayloadSchema = z
  .object({
    protocolVersion: z.number().int().min(1),
    authToken: z.string().max(4096).nullable().optional(),
  })
  .strict();

export const websocketHelloAckPayloadSchema = z
  .object({
    protocolVersion: z.number().int().min(1),
    connectionId: z.string().min(1).max(128),
    principalId: z.string().min(1).max(256),
  })
  .strict();

export const websocketSubscribePayloadSchema = z
  .object({
    runId: runIdSchema,
    channel: z.string().min(1).max(128),
    lastAppliedSequence: sequenceSchema,
  })
  .strict();

export const websocketUnsubscribePayloadSchema = z
  .object({
    runId: runIdSchema,
    channel: z.string().min(1).max(128),
  })
  .strict();

export const websocketPongPayloadSchema = z
  .object({
    serverTime: utcTimestampSchema,
  })
  .strict();

export const websocketSubscribedPayloadSchema = z
  .object({
    runId: runIdSchema,
    channel: z.string().min(1).max(128),
    lastAppliedSequence: sequenceSchema,
    deliveryMode: websocketDeliveryModeSchema,
  })
  .strict();

export const websocketEventPayloadSchema = z
  .object({
    envelope: realtimeMessageEnvelopeSchema,
  })
  .strict();

export const websocketWarningPayloadSchema = z
  .object({
    code: z.string().min(1).max(128),
    message: z.string().min(1).max(2048),
    runId: runIdSchema.nullable().optional(),
    details: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const websocketErrorPayloadSchema = z
  .object({
    error: apiErrorEnvelopeSchema,
  })
  .strict();

export const websocketSnapshotRequiredPayloadSchema = z
  .object({
    runId: runIdSchema,
    reason: websocketErrorCodeSchema,
    fromSequence: sequenceSchema,
    toSequence: sequenceSchema.nullable().optional(),
  })
  .strict();

export const websocketPingPayloadSchema = z
  .object({
    serverTime: utcTimestampSchema,
  })
  .strict();

export const websocketResyncCompletePayloadSchema = z
  .object({
    runId: runIdSchema,
    fromSequence: sequenceSchema,
    toSequence: sequenceSchema,
    eventsDelivered: z.number().int().min(0),
  })
  .strict();

const payloadSchemaByType = {
  hello: websocketHelloPayloadSchema,
  hello_ack: websocketHelloAckPayloadSchema,
  subscribe: websocketSubscribePayloadSchema,
  unsubscribe: websocketUnsubscribePayloadSchema,
  pong: websocketPongPayloadSchema,
  subscribed: websocketSubscribedPayloadSchema,
  event: websocketEventPayloadSchema,
  warning: websocketWarningPayloadSchema,
  error: websocketErrorPayloadSchema,
  snapshot_required: websocketSnapshotRequiredPayloadSchema,
  ping: websocketPingPayloadSchema,
  resync_complete: websocketResyncCompletePayloadSchema,
} as const;

export const websocketFrameSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    protocolVersion: z.number().int().min(1),
    messageType: websocketMessageTypeSchema,
    traceId: traceIdSchema,
    sentAt: utcTimestampSchema,
    payload: z.record(z.string(), z.unknown()),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== WEBSOCKET_FRAME_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported websocket frame schema version: ${String(value.schemaVersion)}`,
      });
    }
    if (value.protocolVersion !== PROTOCOL_VERSION_V1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported websocket protocol version: ${String(value.protocolVersion)}`,
      });
    }
    const payloadSchema = payloadSchemaByType[value.messageType];
    const parsed = payloadSchema.safeParse(value.payload);
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        ctx.addIssue(issue);
      }
    }
  });

export type WebSocketMessageType = z.infer<typeof websocketMessageTypeSchema>;
export type WebSocketErrorCode = z.infer<typeof websocketErrorCodeSchema>;
export type WebSocketDeliveryMode = z.infer<typeof websocketDeliveryModeSchema>;
export type WebSocketFrameV1 = z.infer<typeof websocketFrameSchema>;
export type WebSocketHelloPayloadV1 = z.infer<typeof websocketHelloPayloadSchema>;
export type WebSocketHelloAckPayloadV1 = z.infer<typeof websocketHelloAckPayloadSchema>;
export type WebSocketSubscribePayloadV1 = z.infer<typeof websocketSubscribePayloadSchema>;
export type WebSocketSubscribedPayloadV1 = z.infer<typeof websocketSubscribedPayloadSchema>;
export type WebSocketEventPayloadV1 = z.infer<typeof websocketEventPayloadSchema>;
export type WebSocketSnapshotRequiredPayloadV1 = z.infer<
  typeof websocketSnapshotRequiredPayloadSchema
>;
export type WebSocketResyncCompletePayloadV1 = z.infer<typeof websocketResyncCompletePayloadSchema>;

export function parseWebSocketFrame(value: unknown): WebSocketFrameV1 {
  return websocketFrameSchema.parse(value);
}
