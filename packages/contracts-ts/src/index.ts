import { z } from 'zod';

import {
  agentGraphOverlaySchema,
  candidateAffectedAssetSchema,
  evidenceAttachmentSchema,
  investigationDetailSchema,
  investigationNoteSchema,
  traceInvestigationPlanSchema,
  watchtowerTriageResultSchema,
} from './investigation';

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
import {
  agentArtifactSchema,
  agentBudgetSchema,
  agentDefinitionSchema,
  agentSessionDetailSchema,
  agentStateTransitionSchema,
  agentTaskSchema,
  createAgentSessionRequestSchema,
  createAgentTaskRequestSchema,
  evidenceCitationSchema,
  toolDefinitionSchema,
  toolInvocationSchema,
  toolResultSchema,
} from './agent-runtime';
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

export * from './agent-runtime';
export * from './operator';
export * from './investigation';
export * from './hypothesis';
export * from './proposals';
export * from './approvals';
export * from './reports';
export * from './replay';
export * from './replay-frontend';
export * from './cinematic';
export * from './scoring';
export * from './operator-profile';
export * from './ghost';
export * from './blast-radius';
export * from './auth';
export * from './observability';

import {
  afterActionReportSchema,
  afterActionReportSourceSchema,
  groundingValidationResultSchema,
  reportCitationSchema,
  reportClaimSchema,
  reportExportArtifactSchema,
  reportTimelineEntrySchema,
  reportVersionSchema,
  triggerScribeRequestSchema,
} from './reports';
import {
  approveProposalRequestSchema,
  approveProposalResponseSchema,
  authorizedSimulationCommandSchema,
  cancelProposalRequestSchema,
  cancelProposalResponseSchema,
  executionResultSchema,
  finalPolicyCheckSchema,
  modifyProposalRequestSchema,
  modifyProposalResponseSchema,
  proposalModificationSchema,
  rejectProposalRequestSchema,
  rejectProposalResponseSchema,
  staleProposalErrorSchema,
} from './approvals';
import {
  replayCursorRangeSchema,
  replayCursorSchema,
  replayEquivalenceResultSchema,
  replayProvenanceSchema,
  replaySnapshotSchema,
  replayStateSchema,
  snapshotManifestSchema,
  stateDiffSchema,
} from './replay';
import {
  historicalGraphAdapterSchema,
  replayBookmarkSchema,
  replayComparisonSchema,
  replayViewStateSchema,
  returnToLiveResultSchema,
  timelineFilterSchema,
} from './replay-frontend';
import {
  afterActionViewModelSchema,
  decisionReviewSchema,
  missedEvidenceItemSchema,
  runComparisonSchema,
  runScoreSchema,
  scoreComponentSchema,
  scoreExplanationSchema,
  scoreExportArtifactSchema,
  scoreProvenanceSchema,
  scoreRubricSchema,
  validAlternativeSchema,
} from './scoring';
import {
  authenticatedActorSchema,
  authorizationDecisionSchema,
  permissionContractSchema,
  resourceAccessGrantSchema,
  roleContractSchema,
  securityAuditEventSchema,
  sessionInfoSchema,
} from './auth';
import {
  dependencyStatusSchema,
  healthResponseSchema,
  metricLabelPolicySchema,
  readyResponseSchema,
  structuredLogRecordSchema,
  telemetryContextSchema,
} from './observability';
import {
  consoleAssetDetailSchema,
  consoleEventSearchRequestSchema,
  consoleEventSearchResultSchema,
  createDirectiveRequestSchema,
  operatorActionRequestSchema,
  operatorActionResponseSchema,
  operatorHypothesisRequestSchema,
  roeChangeRequestSchema,
  runFeedEntrySchema,
  runFeedPageSchema,
  standingDirectiveSchema,
} from './operator';
import {
  ghostBranchRequestSchema,
  ghostBranchResultSchema,
  ghostDecisionPointSchema,
  ghostDecisionPointsSchema,
} from './ghost';
import { runLoadoutSchema } from './entities';

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
  agent_definition_v1: agentDefinitionSchema,
  agent_task_v1: agentTaskSchema,
  agent_budget_v1: agentBudgetSchema,
  agent_state_transition_v1: agentStateTransitionSchema,
  tool_definition_v1: toolDefinitionSchema,
  tool_invocation_v1: toolInvocationSchema,
  tool_result_v1: toolResultSchema,
  evidence_citation_v1: evidenceCitationSchema,
  evidence_citation_event_v1: evidenceCitationSchema,
  agent_artifact_v1: agentArtifactSchema,
  create_agent_session_request_v1: createAgentSessionRequestSchema,
  create_agent_task_request_v1: createAgentTaskRequestSchema,
  agent_session_detail_v1: agentSessionDetailSchema,
  watchtower_triage_result_v1: watchtowerTriageResultSchema,
  trace_investigation_plan_v1: traceInvestigationPlanSchema,
  evidence_attachment_v1: evidenceAttachmentSchema,
  candidate_affected_asset_v1: candidateAffectedAssetSchema,
  investigation_note_v1: investigationNoteSchema,
  agent_graph_overlay_v1: agentGraphOverlaySchema,
  investigation_detail_v1: investigationDetailSchema,
  report_citation_v1: reportCitationSchema,
  report_claim_v1: reportClaimSchema,
  report_timeline_entry_v1: reportTimelineEntrySchema,
  after_action_report_source_v1: afterActionReportSourceSchema,
  after_action_report_v1: afterActionReportSchema,
  report_version_v1: reportVersionSchema,
  report_export_artifact_v1: reportExportArtifactSchema,
  grounding_validation_result_v1: groundingValidationResultSchema,
  trigger_scribe_request_v1: triggerScribeRequestSchema,
  stale_proposal_error_v1: staleProposalErrorSchema,
  proposal_modification_v1: proposalModificationSchema,
  final_policy_check_v1: finalPolicyCheckSchema,
  authorized_simulation_command_v1: authorizedSimulationCommandSchema,
  execution_result_v1: executionResultSchema,
  approve_proposal_request_v1: approveProposalRequestSchema,
  reject_proposal_request_v1: rejectProposalRequestSchema,
  modify_proposal_request_v1: modifyProposalRequestSchema,
  cancel_proposal_request_v1: cancelProposalRequestSchema,
  approve_proposal_response_v1: approveProposalResponseSchema,
  reject_proposal_response_v1: rejectProposalResponseSchema,
  modify_proposal_response_v1: modifyProposalResponseSchema,
  cancel_proposal_response_v1: cancelProposalResponseSchema,
  replay_cursor_v1: replayCursorSchema,
  replay_cursor_range_v1: replayCursorRangeSchema,
  replay_provenance_v1: replayProvenanceSchema,
  replay_state_v1: replayStateSchema,
  replay_snapshot_v1: replaySnapshotSchema,
  snapshot_manifest_v1: snapshotManifestSchema,
  state_diff_v1: stateDiffSchema,
  replay_equivalence_result_v1: replayEquivalenceResultSchema,
  replay_view_state_v1: replayViewStateSchema,
  replay_bookmark_v1: replayBookmarkSchema,
  replay_comparison_v1: replayComparisonSchema,
  timeline_filter_v1: timelineFilterSchema,
  historical_graph_adapter_v1: historicalGraphAdapterSchema,
  return_to_live_result_v1: returnToLiveResultSchema,
  score_explanation_v1: scoreExplanationSchema,
  score_rubric_v1: scoreRubricSchema,
  score_component_v1: scoreComponentSchema,
  score_provenance_v1: scoreProvenanceSchema,
  decision_review_v1: decisionReviewSchema,
  missed_evidence_item_v1: missedEvidenceItemSchema,
  valid_alternative_v1: validAlternativeSchema,
  run_score_v1: runScoreSchema,
  after_action_view_model_v1: afterActionViewModelSchema,
  run_comparison_v1: runComparisonSchema,
  score_export_artifact_v1: scoreExportArtifactSchema,
  authenticated_actor_v1: authenticatedActorSchema,
  role_v1: roleContractSchema,
  permission_v1: permissionContractSchema,
  resource_access_grant_v1: resourceAccessGrantSchema,
  authorization_decision_v1: authorizationDecisionSchema,
  session_info_v1: sessionInfoSchema,
  security_audit_event_v1: securityAuditEventSchema,
  telemetry_context_v1: telemetryContextSchema,
  structured_log_record_v1: structuredLogRecordSchema,
  health_response_v1: healthResponseSchema,
  ready_response_v1: readyResponseSchema,
  dependency_status_v1: dependencyStatusSchema,
  metric_label_policy_v1: metricLabelPolicySchema,
  run_loadout_v1: runLoadoutSchema,
  operator_action_request_v1: operatorActionRequestSchema,
  operator_action_response_v1: operatorActionResponseSchema,
  roe_change_request_v1: roeChangeRequestSchema,
  standing_directive_v1: standingDirectiveSchema,
  create_directive_request_v1: createDirectiveRequestSchema,
  console_event_search_request_v1: consoleEventSearchRequestSchema,
  console_event_search_result_v1: consoleEventSearchResultSchema,
  console_asset_detail_v1: consoleAssetDetailSchema,
  operator_hypothesis_request_v1: operatorHypothesisRequestSchema,
  run_feed_entry_v1: runFeedEntrySchema,
  run_feed_page_v1: runFeedPageSchema,
  ghost_decision_point_v1: ghostDecisionPointSchema,
  ghost_decision_points_v1: ghostDecisionPointsSchema,
  ghost_branch_request_v1: ghostBranchRequestSchema,
  ghost_branch_result_v1: ghostBranchResultSchema,
} as const;
