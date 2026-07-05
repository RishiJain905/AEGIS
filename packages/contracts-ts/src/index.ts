import { z } from 'zod';

import {
  backfillRequestSchema,
  backfillResultSchema,
  consumerCursorSchema,
  deadLetterRecordSchema,
  realtimeMessageEnvelopeSchema,
} from './realtime';
import {
  connectionHealthSnapshotSchema,
  runCommandResponseSchema,
  runCreateRequestSchema,
  runReplicatedStateSchema,
  snapshotBootstrapPayloadSchema,
  timelineEntrySchema,
} from './live-run';
import {
  datasetManifestSchema,
  featureComputeRequestSchema,
  featureComputeResponseSchema,
  featureParityCheckResponseSchema,
  featureSchemaManifestSchema,
  featureVectorSchema,
  featureWindowSchema,
  onlineFeatureUpdateSchema,
} from './features';
import {
  anomalyExplanationSchema,
  modelArtifactReferenceSchema,
  modelInferenceResultSchema,
  modelScoreRequestSchema,
  modelScoreResponseSchema,
  modelVerifyArtifactRequestSchema,
  modelVerifyArtifactResponseSchema,
  trainingRunManifestSchema,
} from './models';
import {
  assetRiskScoreSchema,
  riskComputeRequestSchema,
  riskComputeResponseSchema,
  riskContributionSchema,
  riskEngineConfigSchema,
  riskExplanationPathSchema,
  riskInputSchema,
  riskProjectionDeltaSchema,
  riskScoresListResponseSchema,
} from './risk';
import {
  generationArtifactSchema,
  generationRequestSchema,
  generationResponseSchema,
  modelConfigSchema,
  providerCapabilitiesSchema,
  providerErrorSchema,
  providerGenerateRequestSchema,
  providerGenerateResponseSchema,
  providerUsageSchema,
  recordedResponseKeySchema,
  structuredOutputSpecSchema,
  toolSchemaSchema,
} from './generation';
import { websocketFrameSchema } from './websocket';

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
  normalizedEventHashSchema,
  runConfigurationSchema,
  scheduledEventSchema,
  simulationCheckpointSchema,
  simulationCommandSchema,
  worldStateSnapshotSchema,
} from './simulation';
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
export * from './simulation';
export { domainEventEnvelopeSchema } from './events';
export type { DomainEventEnvelopeV1 } from './events';
export * from './graph';
export * from './entities';
export * from './api';
export * from './persistence';
export * from './realtime';
export * from './features';
export * from './detection';
export * from './models';
export * from './risk';
export * from './generation';
export * from './websocket';
export * from './live-run';
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
  run_configuration_v1: runConfigurationSchema,
  scheduled_event_v1: scheduledEventSchema,
  simulation_command_v1: simulationCommandSchema,
  simulation_checkpoint_v1: simulationCheckpointSchema,
  world_state_snapshot_v1: worldStateSnapshotSchema,
  normalized_event_hash_v1: normalizedEventHashSchema,
  realtime_message_envelope_v1: realtimeMessageEnvelopeSchema,
  consumer_cursor_v1: consumerCursorSchema,
  dead_letter_record_v1: deadLetterRecordSchema,
  backfill_request_v1: backfillRequestSchema,
  backfill_result_v1: backfillResultSchema,
  websocket_frame_v1: websocketFrameSchema,
  live_run_v1: runReplicatedStateSchema,
  timeline_entry_v1: timelineEntrySchema,
  snapshot_bootstrap_v1: snapshotBootstrapPayloadSchema,
  run_create_request_v1: runCreateRequestSchema,
  run_command_response_v1: runCommandResponseSchema,
  connection_health_v1: connectionHealthSnapshotSchema,
  feature_schema_manifest_v1: featureSchemaManifestSchema,
  feature_vector_v1: featureVectorSchema,
  feature_window_v1: featureWindowSchema,
  dataset_manifest_v1: datasetManifestSchema,
  online_feature_update_v1: onlineFeatureUpdateSchema,
  feature_compute_request_v1: featureComputeRequestSchema,
  feature_compute_response_v1: featureComputeResponseSchema,
  feature_parity_check_response_v1: featureParityCheckResponseSchema,
  anomaly_explanation_v1: anomalyExplanationSchema,
  training_run_manifest_v1: trainingRunManifestSchema,
  model_artifact_reference_v1: modelArtifactReferenceSchema,
  model_inference_result_v1: modelInferenceResultSchema,
  model_score_request_v1: modelScoreRequestSchema,
  model_score_response_v1: modelScoreResponseSchema,
  model_verify_artifact_request_v1: modelVerifyArtifactRequestSchema,
  model_verify_artifact_response_v1: modelVerifyArtifactResponseSchema,
  risk_input_v1: riskInputSchema,
  risk_engine_config_v1: riskEngineConfigSchema,
  risk_explanation_path_v1: riskExplanationPathSchema,
  risk_contribution_v1: riskContributionSchema,
  asset_risk_score_v1: assetRiskScoreSchema,
  risk_projection_delta_v1: riskProjectionDeltaSchema,
  risk_compute_request_v1: riskComputeRequestSchema,
  risk_compute_response_v1: riskComputeResponseSchema,
  risk_scores_list_response_v1: riskScoresListResponseSchema,
  generation_request_v1: generationRequestSchema,
  generation_response_v1: generationResponseSchema,
  generation_artifact_v1: generationArtifactSchema,
  model_config_v1: modelConfigSchema,
  provider_usage_v1: providerUsageSchema,
  provider_error_v1: providerErrorSchema,
  recorded_response_key_v1: recordedResponseKeySchema,
  provider_generate_request_v1: providerGenerateRequestSchema,
  provider_generate_response_v1: providerGenerateResponseSchema,
  provider_capabilities_v1: providerCapabilitiesSchema,
  structured_output_spec_v1: structuredOutputSpecSchema,
  tool_schema_v1: toolSchemaSchema,
} as const;
