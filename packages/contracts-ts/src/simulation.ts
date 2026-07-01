import { z } from 'zod';

import { ContractErrorCode, ContractValidationError } from './errors';
import { actorRefSchema } from './events';
import {
  authoredIdSchema,
  runIdSchema,
  sequenceSchema,
  simTimestampSchema,
  utcTimestampSchema,
} from './primitives';
import {
  NORMALIZED_EVENT_HASH_SCHEMA_VERSION,
  RUN_CONFIGURATION_SCHEMA_VERSION,
  SCHEDULED_EVENT_SCHEMA_VERSION,
  SIMULATION_CHECKPOINT_SCHEMA_VERSION,
  SIMULATION_COMMAND_SCHEMA_VERSION,
  WORLD_STATE_SNAPSHOT_SCHEMA_VERSION,
} from './versioning';

export const SimulationRunStatus = {
  CREATED: 'created',
  RUNNING: 'running',
  PAUSED: 'paused',
  STOPPED: 'stopped',
} as const;

export const SimulationCommandType = {
  START: 'start',
  STEP: 'step',
  ADVANCE: 'advance',
  PAUSE: 'pause',
  RESUME: 'resume',
  STOP: 'stop',
  CHECKPOINT: 'checkpoint',
  RESTORE: 'restore',
  EXECUTE: 'execute',
} as const;

export const ScheduledEventSourceType = {
  SCHEDULED: 'scheduled',
  GENERATOR: 'generator',
} as const;

export const runConfigurationSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    scenarioVersionId: authoredIdSchema,
    seed: z.number().int(),
    engineVersion: z.string().min(1),
    initialSimTime: simTimestampSchema,
    recordedAtEpoch: simTimestampSchema,
    maxSteps: z.number().int().min(1).nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== RUN_CONFIGURATION_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported run configuration schema version: ${value.schemaVersion}`,
      });
    }
  });

export const scheduledEventSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    eventId: z.string().min(1),
    simTime: simTimestampSchema,
    priority: z.number().int().min(0),
    tieBreaker: z.number().int().min(0),
    sourceType: z.enum(['scheduled', 'generator']),
    pluginId: z.string().min(1),
    config: z.record(z.unknown()).default({}),
    targetAssetId: authoredIdSchema.nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== SCHEDULED_EVENT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported scheduled event schema version: ${value.schemaVersion}`,
      });
    }
  });

export const simulationCommandSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    commandId: z.string().min(1),
    commandType: z.enum([
      'start',
      'step',
      'advance',
      'pause',
      'resume',
      'stop',
      'checkpoint',
      'restore',
      'execute',
    ]),
    runId: runIdSchema,
    actor: actorRefSchema,
    authorizationToken: z.string().nullable().optional(),
    payload: z.record(z.unknown()).default({}),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== SIMULATION_COMMAND_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported simulation command schema version: ${value.schemaVersion}`,
      });
    }
  });

const assetInstanceSnapshotSchema = z
  .object({
    id: authoredIdSchema,
    assetType: z.string().min(1),
    status: z.string().min(1),
    riskScore: z.number().min(0).max(1),
    criticality: z.number().min(0).max(1),
    zoneId: z.string().min(1),
    revision: z.number().int().min(0),
  })
  .strict();

const relationshipInstanceSnapshotSchema = z
  .object({
    id: authoredIdSchema,
    sourceId: authoredIdSchema,
    targetId: authoredIdSchema,
    relationshipType: z.string().min(1),
    confidence: z.number().min(0).max(1),
    riskContribution: z.number().min(0).max(1),
    revision: z.number().int().min(0),
  })
  .strict();

const generatorStateSnapshotSchema = z
  .object({
    generatorId: z.string().min(1),
    targetAssetId: authoredIdSchema,
    pluginId: z.string().min(1),
    config: z.record(z.unknown()).default({}),
    nextSimTime: simTimestampSchema,
    intervalSimSeconds: z.number().int().min(1),
    jitterSimSeconds: z.number().int().min(0),
  })
  .strict();

const hiddenConditionStateSnapshotSchema = z
  .object({
    conditionId: z.string().min(1),
    revealed: z.boolean(),
    triggered: z.boolean(),
  })
  .strict();

export const worldStateSnapshotSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    status: z.enum(['created', 'running', 'paused', 'stopped']),
    simTime: simTimestampSchema,
    nextSequence: sequenceSchema.min(1),
    assets: z.array(assetInstanceSnapshotSchema),
    relationships: z.array(relationshipInstanceSnapshotSchema),
    generators: z.array(generatorStateSnapshotSchema),
    hiddenConditions: z.array(hiddenConditionStateSnapshotSchema).default([]),
    selectedBranches: z.record(z.string()).default({}),
    pendingEvents: z.array(scheduledEventSchema).default([]),
    rngState: z.record(z.array(z.number().int())).default({}),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== WORLD_STATE_SNAPSHOT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported world state snapshot schema version: ${value.schemaVersion}`,
      });
    }
  });

export const simulationCheckpointSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    id: z.string().min(1),
    runId: runIdSchema,
    sequenceAtCheckpoint: sequenceSchema,
    engineVersion: z.string().min(1),
    checksum: z.string().min(1),
    worldState: worldStateSnapshotSchema,
    createdAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== SIMULATION_CHECKPOINT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported simulation checkpoint schema version: ${value.schemaVersion}`,
      });
    }
  });

export const normalizedEventHashSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    scenarioVersionId: authoredIdSchema,
    seed: z.number().int(),
    engineVersion: z.string().min(1),
    hash: z.string().min(1),
    eventCount: z.number().int().min(0),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== NORMALIZED_EVENT_HASH_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported normalized event hash schema version: ${value.schemaVersion}`,
      });
    }
  });

export type RunConfigurationV1 = z.infer<typeof runConfigurationSchema>;
export type ScheduledEventV1 = z.infer<typeof scheduledEventSchema>;
export type SimulationCommandV1 = z.infer<typeof simulationCommandSchema>;
export type WorldStateSnapshotV1 = z.infer<typeof worldStateSnapshotSchema>;
export type SimulationCheckpointV1 = z.infer<typeof simulationCheckpointSchema>;
export type NormalizedEventHashV1 = z.infer<typeof normalizedEventHashSchema>;

export function assertSimulationSchemaVersion(contractName: string, schemaVersion: number): void {
  const supported: Record<string, number> = {
    run_configuration: RUN_CONFIGURATION_SCHEMA_VERSION,
    scheduled_event: SCHEDULED_EVENT_SCHEMA_VERSION,
    simulation_command: SIMULATION_COMMAND_SCHEMA_VERSION,
    simulation_checkpoint: SIMULATION_CHECKPOINT_SCHEMA_VERSION,
    world_state_snapshot: WORLD_STATE_SNAPSHOT_SCHEMA_VERSION,
    normalized_event_hash: NORMALIZED_EVENT_HASH_SCHEMA_VERSION,
  };
  const expected = supported[contractName];
  if (expected === undefined) {
    throw new ContractValidationError({
      code: ContractErrorCode.VALIDATION_FAILED,
      message: `Unknown contract name: ${contractName}`,
      details: { contractName },
    });
  }
  if (schemaVersion !== expected) {
    throw new ContractValidationError({
      code: ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
      message: `Unsupported schema version ${schemaVersion} for contract ${contractName}`,
      details: { contractName, schemaVersion, supportedVersions: [expected] },
    });
  }
}
