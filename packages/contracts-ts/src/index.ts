import { z } from 'zod';

import { cursorPaginationSchema, idempotencyMetadataSchema } from './api';
import { idempotencyRecordSchema, objectMetadataReferenceSchema } from './persistence';
import {
  actionProposalSchema,
  agentSessionSchema,
  alertSchema,
  approvalSchema,
  evidenceSchema,
  executedActionSchema,
  hypothesisSchema,
  incidentSchema,
  modelManifestSchema,
  modelScoreSchema,
  runSchema,
  scenarioSchema,
  scenarioVersionSchema,
} from './entities';
import { apiErrorEnvelopeSchema } from './errors';
import { domainEventEnvelopeSchema } from './events';
import {
  graphDeltaSchema,
  graphEdgeSchema,
  graphNodeSchema,
  graphPathQuerySchema,
  graphPathResultSchema,
  graphSnapshotSchema,
} from './graph';

export { WORKSPACE_VERSION, SUPPORTED_SCHEMA_VERSIONS } from './versioning';
export * from './versioning';
export * from './errors';
export * from './primitives';
export * from './events';
export * from './graph';
export * from './entities';
export * from './api';
export * from './persistence';
export * from './parsing';

export const aegisEnvironmentSchema = z.object({
  AEGIS_ENV: z.enum(['development', 'test', 'production']),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']),
  POSTGRES_HOST: z.string().min(1),
  POSTGRES_PORT: z.coerce.number().int().positive(),
  POSTGRES_DB: z.string().min(1),
  POSTGRES_USER: z.string().min(1),
  POSTGRES_PASSWORD: z.string().min(1),
  REDIS_URL: z.string().url(),
  S3_ENDPOINT: z.string().url(),
  S3_ACCESS_KEY: z.string().min(1),
  S3_SECRET_KEY: z.string().min(1),
  S3_BUCKET: z.string().min(1),
  API_PORT: z.coerce.number().int().positive(),
  WEB_PORT: z.coerce.number().int().positive(),
});

export type AegisEnvironment = z.infer<typeof aegisEnvironmentSchema>;

export function parseAegisEnvironment(env: Record<string, string | undefined>): AegisEnvironment {
  return aegisEnvironmentSchema.parse(env);
}

export function safeParseAegisEnvironment(env: Record<string, string | undefined>) {
  return aegisEnvironmentSchema.safeParse(env);
}

export const FIXTURE_SCHEMA_MAP = {
  event_envelope_v1: domainEventEnvelopeSchema,
  graph_node_v1: graphNodeSchema,
  graph_edge_v1: graphEdgeSchema,
  graph_snapshot_v1: graphSnapshotSchema,
  graph_delta_v1: graphDeltaSchema,
  graph_path_query_v1: graphPathQuerySchema,
  graph_path_result_v1: graphPathResultSchema,
  api_error_v1: apiErrorEnvelopeSchema,
  cursor_page_v1: cursorPaginationSchema,
  idempotency_v1: idempotencyMetadataSchema,
  idempotency_record_v1: idempotencyRecordSchema,
  object_metadata_reference_v1: objectMetadataReferenceSchema,
  scenario_v1: scenarioSchema,
  scenario_version_v1: scenarioVersionSchema,
  run_v1: runSchema,
  alert_v1: alertSchema,
  incident_v1: incidentSchema,
  evidence_v1: evidenceSchema,
  hypothesis_v1: hypothesisSchema,
  agent_session_v1: agentSessionSchema,
  action_proposal_v1: actionProposalSchema,
  approval_v1: approvalSchema,
  executed_action_v1: executedActionSchema,
  model_manifest_v1: modelManifestSchema,
  model_score_v1: modelScoreSchema,
} as const;
