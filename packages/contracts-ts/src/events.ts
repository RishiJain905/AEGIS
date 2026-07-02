import { z } from 'zod';

import { ContractErrorCode, ContractValidationError } from './errors';
import {
  authoredIdSchema,
  causationIdSchema,
  correlationIdSchema,
  eventIdSchema,
  runIdSchema,
  sequenceSchema,
  simTimestampSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import { DOMAIN_EVENT_SCHEMA_VERSION } from './versioning';

export const ActorType = {
  ASSET: 'asset',
  AGENT: 'agent',
  SYSTEM: 'system',
  OPERATOR: 'operator',
} as const;

export const actorRefSchema = z
  .object({
    type: z.enum(['asset', 'agent', 'system', 'operator']),
    id: authoredIdSchema,
  })
  .strict();

export const EVENT_TYPE_REGISTRY: Readonly<Record<string, number>> = {
  'sim.run.started': 1,
  'sim.run.paused': 1,
  'sim.run.resumed': 1,
  'sim.run.stopped': 1,
  'sim.checkpoint.created': 1,
  'sim.command.executed': 1,
  'sim.asset.status_changed': 1,
  'sim.branch.selected': 1,
  'sim.hidden_condition.revealed': 1,
  'sim.hidden_condition.triggered': 1,
  'telemetry.authentication.failed': 1,
  'telemetry.authentication.succeeded': 1,
  'telemetry.api.request': 1,
  'telemetry.health.check': 1,
  'telemetry.network.connection': 1,
  'telemetry.database.query': 1,
  'telemetry.deployment.event': 1,
  'telemetry.process.activity': 1,
  'telemetry.ai.inference': 1,
  'alert.created': 1,
  'incident.created': 1,
  'incident.state_changed': 1,
  'hypothesis.created': 1,
  'agent.session.started': 1,
  'agent.session.completed': 1,
  'action.proposal.created': 1,
  'action.proposal.approved': 1,
  'action.executed': 1,
  'graph.snapshot.created': 1,
  'model.score.recorded': 1,
  'risk.score.computed': 1,
  'risk.projection.updated': 1,
};

export function isKnownEventType(eventType: string): boolean {
  return eventType in EVENT_TYPE_REGISTRY;
}

export function payloadSchemaVersion(eventType: string): number {
  const version = EVENT_TYPE_REGISTRY[eventType];
  if (version === undefined) {
    throw new ContractValidationError({
      code: ContractErrorCode.VALIDATION_FAILED,
      message: `Unknown event type: ${eventType}`,
      details: { type: eventType },
    });
  }
  return version;
}

export const domainEventEnvelopeSchema = z
  .object({
    eventId: eventIdSchema,
    runId: runIdSchema,
    sequence: sequenceSchema,
    type: z.string().min(1),
    schemaVersion: z.number().int().min(1),
    simTime: simTimestampSchema,
    recordedAt: utcTimestampSchema,
    actor: actorRefSchema,
    subject: actorRefSchema,
    payload: z.record(z.unknown()).default({}),
    traceId: traceIdSchema,
    causationId: causationIdSchema.nullable().optional(),
    correlationId: correlationIdSchema.nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (!isKnownEventType(value.type)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unknown event type: ${value.type}`,
      });
      return;
    }
    if (value.schemaVersion !== DOMAIN_EVENT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported domain event schema version: ${String(value.schemaVersion)}`,
      });
      return;
    }
    const expectedPayloadVersion = payloadSchemaVersion(value.type);
    const payloadVersion = value.payload.schemaVersion;
    if (
      payloadVersion !== undefined &&
      typeof payloadVersion === 'number' &&
      payloadVersion !== expectedPayloadVersion
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Event payload schema version mismatch',
      });
    }
  });

export type DomainEventEnvelopeV1 = z.infer<typeof domainEventEnvelopeSchema>;

export const EventTypeRegistry = {
  isKnownType: isKnownEventType,
  payloadSchemaVersion,
  knownTypes: (): ReadonlySet<string> => new Set(Object.keys(EVENT_TYPE_REGISTRY)),
};
