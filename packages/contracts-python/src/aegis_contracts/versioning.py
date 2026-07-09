"""Schema and protocol version constants for AEGIS shared contracts."""

from __future__ import annotations

from typing import Final

from aegis_contracts.errors import ContractErrorCode, ContractValidationError

WORKSPACE_VERSION: Final[str] = "0.0.0-phase24"

PROTOCOL_VERSION_V1: Final[int] = 1

DOMAIN_EVENT_SCHEMA_VERSION: Final[int] = 1
GRAPH_NODE_SCHEMA_VERSION: Final[int] = 1
GRAPH_EDGE_SCHEMA_VERSION: Final[int] = 1
GRAPH_SNAPSHOT_SCHEMA_VERSION: Final[int] = 1
GRAPH_DELTA_SCHEMA_VERSION: Final[int] = 1
GRAPH_PATH_QUERY_SCHEMA_VERSION: Final[int] = 1
GRAPH_PATH_RESULT_SCHEMA_VERSION: Final[int] = 1
API_ERROR_SCHEMA_VERSION: Final[int] = 1
CURSOR_PAGINATION_SCHEMA_VERSION: Final[int] = 1
IDEMPOTENCY_SCHEMA_VERSION: Final[int] = 1
IDEMPOTENCY_RECORD_SCHEMA_VERSION: Final[int] = 1
OBJECT_METADATA_REFERENCE_SCHEMA_VERSION: Final[int] = 1
SCENARIO_SCHEMA_VERSION: Final[int] = 1
SCENARIO_VERSION_SCHEMA_VERSION: Final[int] = 1
RUN_SCHEMA_VERSION: Final[int] = 1
ALERT_SCHEMA_VERSION: Final[int] = 1
INCIDENT_SCHEMA_VERSION: Final[int] = 1
EVIDENCE_SCHEMA_VERSION: Final[int] = 1
HYPOTHESIS_SCHEMA_VERSION: Final[int] = 2
AGENT_SESSION_SCHEMA_VERSION: Final[int] = 1
ACTION_PROPOSAL_SCHEMA_VERSION: Final[int] = 2
APPROVAL_SCHEMA_VERSION: Final[int] = 1
EXECUTED_ACTION_SCHEMA_VERSION: Final[int] = 1
MODEL_MANIFEST_SCHEMA_VERSION: Final[int] = 1
MODEL_SCORE_SCHEMA_VERSION: Final[int] = 1
RUN_CONFIGURATION_SCHEMA_VERSION: Final[int] = 1
SCHEDULED_EVENT_SCHEMA_VERSION: Final[int] = 1
SIMULATION_COMMAND_SCHEMA_VERSION: Final[int] = 1
SIMULATION_CHECKPOINT_SCHEMA_VERSION: Final[int] = 1
WORLD_STATE_SNAPSHOT_SCHEMA_VERSION: Final[int] = 1
NORMALIZED_EVENT_HASH_SCHEMA_VERSION: Final[int] = 1
REALTIME_MESSAGE_SCHEMA_VERSION: Final[int] = 1
CONSUMER_CURSOR_SCHEMA_VERSION: Final[int] = 1
DEAD_LETTER_RECORD_SCHEMA_VERSION: Final[int] = 1
BACKFILL_REQUEST_SCHEMA_VERSION: Final[int] = 1
BACKFILL_RESULT_SCHEMA_VERSION: Final[int] = 1
WEBSOCKET_FRAME_SCHEMA_VERSION: Final[int] = 1
LIVE_RUN_SCHEMA_VERSION: Final[int] = 1
TIMELINE_ENTRY_SCHEMA_VERSION: Final[int] = 1
SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION: Final[int] = 1
RUN_CREATE_REQUEST_SCHEMA_VERSION: Final[int] = 1
RUN_COMMAND_RESPONSE_SCHEMA_VERSION: Final[int] = 1
CONNECTION_HEALTH_SCHEMA_VERSION: Final[int] = 1
REALTIME_REDUCER_ACTION_SCHEMA_VERSION: Final[int] = 1
FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION: Final[int] = 1
FEATURE_VECTOR_SCHEMA_VERSION: Final[int] = 1
FEATURE_WINDOW_SCHEMA_VERSION: Final[int] = 1
FEATURE_PROVENANCE_SCHEMA_VERSION: Final[int] = 1
DATASET_MANIFEST_SCHEMA_VERSION: Final[int] = 1
ONLINE_FEATURE_UPDATE_SCHEMA_VERSION: Final[int] = 1
FEATURE_COMPUTE_REQUEST_SCHEMA_VERSION: Final[int] = 1
FEATURE_COMPUTE_RESPONSE_SCHEMA_VERSION: Final[int] = 1
FEATURE_PARITY_CHECK_RESPONSE_SCHEMA_VERSION: Final[int] = 1
FEATURE_SCHEMA_VERSION: Final[int] = 1
DETECTION_RULE_SCHEMA_VERSION: Final[int] = 1
DETECTION_RULE_REGISTRY_SCHEMA_VERSION: Final[int] = 1
RULE_THRESHOLD_SCHEMA_VERSION: Final[int] = 1
STATISTICAL_BASELINE_SCHEMA_VERSION: Final[int] = 1
STATISTICAL_BASELINE_MANIFEST_SCHEMA_VERSION: Final[int] = 1
RULE_EXPLANATION_SCHEMA_VERSION: Final[int] = 1
ALERT_CANDIDATE_SCHEMA_VERSION: Final[int] = 1
RULE_EVALUATION_SCHEMA_VERSION: Final[int] = 1
METRIC_REPORT_SCHEMA_VERSION: Final[int] = 1
EVALUATION_RUN_SCHEMA_VERSION: Final[int] = 1
DETECTION_EVALUATE_REQUEST_SCHEMA_VERSION: Final[int] = 1
DETECTION_EVALUATE_RESPONSE_SCHEMA_VERSION: Final[int] = 1
ANOMALY_EXPLANATION_SCHEMA_VERSION: Final[int] = 1
MODEL_ARTIFACT_REFERENCE_SCHEMA_VERSION: Final[int] = 1
TRAINING_RUN_MANIFEST_SCHEMA_VERSION: Final[int] = 1
MODEL_INFERENCE_RESULT_SCHEMA_VERSION: Final[int] = 1
MODEL_EVALUATE_REQUEST_SCHEMA_VERSION: Final[int] = 1
MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION: Final[int] = 1
MODEL_VERIFY_ARTIFACT_REQUEST_SCHEMA_VERSION: Final[int] = 1
MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION: Final[int] = 1
RISK_INPUT_SCHEMA_VERSION: Final[int] = 1
RISK_ENGINE_CONFIG_SCHEMA_VERSION: Final[int] = 1
RISK_EXPLANATION_PATH_SCHEMA_VERSION: Final[int] = 1
RISK_CONTRIBUTION_SCHEMA_VERSION: Final[int] = 1
ASSET_RISK_SCORE_SCHEMA_VERSION: Final[int] = 1
RISK_PROJECTION_DELTA_SCHEMA_VERSION: Final[int] = 1
RISK_COMPUTE_REQUEST_SCHEMA_VERSION: Final[int] = 1
RISK_COMPUTE_RESPONSE_SCHEMA_VERSION: Final[int] = 1
RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION: Final[int] = 1
GENERATION_REQUEST_SCHEMA_VERSION: Final[int] = 1
GENERATION_RESPONSE_SCHEMA_VERSION: Final[int] = 1
STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION: Final[int] = 1
TOOL_SCHEMA_SCHEMA_VERSION: Final[int] = 1
PROVIDER_CAPABILITIES_SCHEMA_VERSION: Final[int] = 1
MODEL_CONFIG_SCHEMA_VERSION: Final[int] = 1
PROVIDER_USAGE_SCHEMA_VERSION: Final[int] = 1
PROVIDER_ERROR_SCHEMA_VERSION: Final[int] = 1
RECORDED_RESPONSE_KEY_SCHEMA_VERSION: Final[int] = 1
GENERATION_ARTIFACT_SCHEMA_VERSION: Final[int] = 1
PROVIDER_GENERATE_REQUEST_SCHEMA_VERSION: Final[int] = 1
PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION: Final[int] = 1
AGENT_DEFINITION_SCHEMA_VERSION: Final[int] = 1
AGENT_TASK_SCHEMA_VERSION: Final[int] = 1
AGENT_STATE_TRANSITION_SCHEMA_VERSION: Final[int] = 1
TOOL_DEFINITION_SCHEMA_VERSION: Final[int] = 1
TOOL_INVOCATION_SCHEMA_VERSION: Final[int] = 1
TOOL_RESULT_SCHEMA_VERSION: Final[int] = 1
EVIDENCE_CITATION_SCHEMA_VERSION: Final[int] = 1
AGENT_BUDGET_SCHEMA_VERSION: Final[int] = 1
AGENT_ARTIFACT_SCHEMA_VERSION: Final[int] = 1
CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION: Final[int] = 1
CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION: Final[int] = 1
AGENT_SESSION_DETAIL_SCHEMA_VERSION: Final[int] = 1
WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION: Final[int] = 1
TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION: Final[int] = 1
EVIDENCE_ATTACHMENT_SCHEMA_VERSION: Final[int] = 1
CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION: Final[int] = 1
INVESTIGATION_NOTE_SCHEMA_VERSION: Final[int] = 1
AGENT_GRAPH_OVERLAY_SCHEMA_VERSION: Final[int] = 1
INVESTIGATION_DETAIL_SCHEMA_VERSION: Final[int] = 4
TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION: Final[int] = 1
HYPOTHESIS_CLAIM_SCHEMA_VERSION: Final[int] = 1
CONFIDENCE_ASSESSMENT_SCHEMA_VERSION: Final[int] = 1
CONTRADICTION_LINK_SCHEMA_VERSION: Final[int] = 1
HYPOTHESIS_REVISION_SCHEMA_VERSION: Final[int] = 1
HYPOTHESIS_COMPARISON_SCHEMA_VERSION: Final[int] = 1
VERIFICATION_REQUEST_SCHEMA_VERSION: Final[int] = 1
TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION: Final[int] = 1
RESPONSE_OPTION_SCHEMA_VERSION: Final[int] = 1
PROPOSAL_REVISION_SCHEMA_VERSION: Final[int] = 1
POLICY_INPUT_SCHEMA_VERSION: Final[int] = 1
POLICY_DECISION_SCHEMA_VERSION: Final[int] = 1
APPROVAL_REQUIREMENT_SCHEMA_VERSION: Final[int] = 1
TRIGGER_BASTION_REQUEST_SCHEMA_VERSION: Final[int] = 1
TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION: Final[int] = 1
REPORT_CITATION_SCHEMA_VERSION: Final[int] = 1
REPORT_CLAIM_SCHEMA_VERSION: Final[int] = 1
REPORT_TIMELINE_ENTRY_SCHEMA_VERSION: Final[int] = 1
AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION: Final[int] = 1
AFTER_ACTION_REPORT_SCHEMA_VERSION: Final[int] = 1
REPORT_VERSION_SCHEMA_VERSION: Final[int] = 1
REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION: Final[int] = 1
GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION: Final[int] = 1
TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION: Final[int] = 1
STALE_PROPOSAL_ERROR_SCHEMA_VERSION: Final[int] = 1
PROPOSAL_MODIFICATION_SCHEMA_VERSION: Final[int] = 1
FINAL_POLICY_CHECK_SCHEMA_VERSION: Final[int] = 1
AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION: Final[int] = 1
EXECUTION_RESULT_SCHEMA_VERSION: Final[int] = 1
APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION: Final[int] = 1
REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION: Final[int] = 1
MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION: Final[int] = 1
CANCEL_PROPOSAL_REQUEST_SCHEMA_VERSION: Final[int] = 1
APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION: Final[int] = 1
REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION: Final[int] = 1
MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION: Final[int] = 1

SUPPORTED_SCHEMA_VERSIONS: Final[dict[str, frozenset[int]]] = {
    "domain_event": frozenset({DOMAIN_EVENT_SCHEMA_VERSION}),
    "graph_node": frozenset({GRAPH_NODE_SCHEMA_VERSION}),
    "graph_edge": frozenset({GRAPH_EDGE_SCHEMA_VERSION}),
    "graph_snapshot": frozenset({GRAPH_SNAPSHOT_SCHEMA_VERSION}),
    "graph_delta": frozenset({GRAPH_DELTA_SCHEMA_VERSION}),
    "graph_path_query": frozenset({GRAPH_PATH_QUERY_SCHEMA_VERSION}),
    "graph_path_result": frozenset({GRAPH_PATH_RESULT_SCHEMA_VERSION}),
    "api_error": frozenset({API_ERROR_SCHEMA_VERSION}),
    "cursor_pagination": frozenset({CURSOR_PAGINATION_SCHEMA_VERSION}),
    "idempotency": frozenset({IDEMPOTENCY_SCHEMA_VERSION}),
    "idempotency_record": frozenset({IDEMPOTENCY_RECORD_SCHEMA_VERSION}),
    "object_metadata_reference": frozenset({OBJECT_METADATA_REFERENCE_SCHEMA_VERSION}),
    "scenario": frozenset({SCENARIO_SCHEMA_VERSION}),
    "scenario_version": frozenset({SCENARIO_VERSION_SCHEMA_VERSION}),
    "run": frozenset({RUN_SCHEMA_VERSION}),
    "alert": frozenset({ALERT_SCHEMA_VERSION}),
    "incident": frozenset({INCIDENT_SCHEMA_VERSION}),
    "evidence": frozenset({EVIDENCE_SCHEMA_VERSION}),
    "hypothesis": frozenset({1, HYPOTHESIS_SCHEMA_VERSION}),
    "hypothesis_claim": frozenset({HYPOTHESIS_CLAIM_SCHEMA_VERSION}),
    "confidence_assessment": frozenset({CONFIDENCE_ASSESSMENT_SCHEMA_VERSION}),
    "contradiction_link": frozenset({CONTRADICTION_LINK_SCHEMA_VERSION}),
    "hypothesis_revision": frozenset({HYPOTHESIS_REVISION_SCHEMA_VERSION}),
    "hypothesis_comparison": frozenset({HYPOTHESIS_COMPARISON_SCHEMA_VERSION}),
    "verification_request": frozenset({VERIFICATION_REQUEST_SCHEMA_VERSION}),
    "trigger_oracle_request": frozenset({TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION}),
    "agent_session": frozenset({AGENT_SESSION_SCHEMA_VERSION}),
    "action_proposal": frozenset({1, ACTION_PROPOSAL_SCHEMA_VERSION}),
    "response_option": frozenset({RESPONSE_OPTION_SCHEMA_VERSION}),
    "proposal_revision": frozenset({PROPOSAL_REVISION_SCHEMA_VERSION}),
    "policy_input": frozenset({POLICY_INPUT_SCHEMA_VERSION}),
    "policy_decision": frozenset({POLICY_DECISION_SCHEMA_VERSION}),
    "approval_requirement": frozenset({APPROVAL_REQUIREMENT_SCHEMA_VERSION}),
    "trigger_bastion_request": frozenset({TRIGGER_BASTION_REQUEST_SCHEMA_VERSION}),
    "trigger_warden_request": frozenset({TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION}),
    "report_citation": frozenset({REPORT_CITATION_SCHEMA_VERSION}),
    "report_claim": frozenset({REPORT_CLAIM_SCHEMA_VERSION}),
    "report_timeline_entry": frozenset({REPORT_TIMELINE_ENTRY_SCHEMA_VERSION}),
    "after_action_report_source": frozenset({AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION}),
    "after_action_report": frozenset({AFTER_ACTION_REPORT_SCHEMA_VERSION}),
    "report_version": frozenset({REPORT_VERSION_SCHEMA_VERSION}),
    "report_export_artifact": frozenset({REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION}),
    "grounding_validation_result": frozenset({GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION}),
    "trigger_scribe_request": frozenset({TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION}),
    "approval": frozenset({APPROVAL_SCHEMA_VERSION}),
    "executed_action": frozenset({EXECUTED_ACTION_SCHEMA_VERSION}),
    "model_manifest": frozenset({MODEL_MANIFEST_SCHEMA_VERSION}),
    "model_score": frozenset({MODEL_SCORE_SCHEMA_VERSION}),
    "run_configuration": frozenset({RUN_CONFIGURATION_SCHEMA_VERSION}),
    "scheduled_event": frozenset({SCHEDULED_EVENT_SCHEMA_VERSION}),
    "simulation_command": frozenset({SIMULATION_COMMAND_SCHEMA_VERSION}),
    "simulation_checkpoint": frozenset({SIMULATION_CHECKPOINT_SCHEMA_VERSION}),
    "world_state_snapshot": frozenset({WORLD_STATE_SNAPSHOT_SCHEMA_VERSION}),
    "normalized_event_hash": frozenset({NORMALIZED_EVENT_HASH_SCHEMA_VERSION}),
    "realtime_message": frozenset({REALTIME_MESSAGE_SCHEMA_VERSION}),
    "consumer_cursor": frozenset({CONSUMER_CURSOR_SCHEMA_VERSION}),
    "dead_letter_record": frozenset({DEAD_LETTER_RECORD_SCHEMA_VERSION}),
    "backfill_request": frozenset({BACKFILL_REQUEST_SCHEMA_VERSION}),
    "backfill_result": frozenset({BACKFILL_RESULT_SCHEMA_VERSION}),
    "websocket_frame": frozenset({WEBSOCKET_FRAME_SCHEMA_VERSION}),
    "live_run": frozenset({LIVE_RUN_SCHEMA_VERSION}),
    "timeline_entry": frozenset({TIMELINE_ENTRY_SCHEMA_VERSION}),
    "snapshot_bootstrap": frozenset({SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION}),
    "run_create_request": frozenset({RUN_CREATE_REQUEST_SCHEMA_VERSION}),
    "run_command_response": frozenset({RUN_COMMAND_RESPONSE_SCHEMA_VERSION}),
    "connection_health": frozenset({CONNECTION_HEALTH_SCHEMA_VERSION}),
    "feature_schema_manifest": frozenset({FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION}),
    "feature_vector": frozenset({FEATURE_VECTOR_SCHEMA_VERSION}),
    "feature_window": frozenset({FEATURE_WINDOW_SCHEMA_VERSION}),
    "feature_provenance": frozenset({FEATURE_PROVENANCE_SCHEMA_VERSION}),
    "dataset_manifest": frozenset({DATASET_MANIFEST_SCHEMA_VERSION}),
    "online_feature_update": frozenset({ONLINE_FEATURE_UPDATE_SCHEMA_VERSION}),
    "detection_rule": frozenset({DETECTION_RULE_SCHEMA_VERSION}),
    "detection_rule_registry": frozenset({DETECTION_RULE_REGISTRY_SCHEMA_VERSION}),
    "rule_threshold": frozenset({RULE_THRESHOLD_SCHEMA_VERSION}),
    "statistical_baseline": frozenset({STATISTICAL_BASELINE_SCHEMA_VERSION}),
    "statistical_baseline_manifest": frozenset({STATISTICAL_BASELINE_MANIFEST_SCHEMA_VERSION}),
    "rule_explanation": frozenset({RULE_EXPLANATION_SCHEMA_VERSION}),
    "alert_candidate": frozenset({ALERT_CANDIDATE_SCHEMA_VERSION}),
    "rule_evaluation": frozenset({RULE_EVALUATION_SCHEMA_VERSION}),
    "metric_report": frozenset({METRIC_REPORT_SCHEMA_VERSION}),
    "evaluation_run": frozenset({EVALUATION_RUN_SCHEMA_VERSION}),
    "anomaly_explanation": frozenset({ANOMALY_EXPLANATION_SCHEMA_VERSION}),
    "model_artifact_reference": frozenset({MODEL_ARTIFACT_REFERENCE_SCHEMA_VERSION}),
    "training_run_manifest": frozenset({TRAINING_RUN_MANIFEST_SCHEMA_VERSION}),
    "model_inference_result": frozenset({MODEL_INFERENCE_RESULT_SCHEMA_VERSION}),
    "model_evaluate_request": frozenset({MODEL_EVALUATE_REQUEST_SCHEMA_VERSION}),
    "model_evaluate_response": frozenset({MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION}),
    "model_verify_artifact_request": frozenset({MODEL_VERIFY_ARTIFACT_REQUEST_SCHEMA_VERSION}),
    "model_verify_artifact_response": frozenset({MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION}),
    "risk_input": frozenset({RISK_INPUT_SCHEMA_VERSION}),
    "risk_engine_config": frozenset({RISK_ENGINE_CONFIG_SCHEMA_VERSION}),
    "risk_explanation_path": frozenset({RISK_EXPLANATION_PATH_SCHEMA_VERSION}),
    "risk_contribution": frozenset({RISK_CONTRIBUTION_SCHEMA_VERSION}),
    "asset_risk_score": frozenset({ASSET_RISK_SCORE_SCHEMA_VERSION}),
    "risk_projection_delta": frozenset({RISK_PROJECTION_DELTA_SCHEMA_VERSION}),
    "risk_compute_request": frozenset({RISK_COMPUTE_REQUEST_SCHEMA_VERSION}),
    "risk_compute_response": frozenset({RISK_COMPUTE_RESPONSE_SCHEMA_VERSION}),
    "risk_scores_list_response": frozenset({RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION}),
    "generation_request": frozenset({GENERATION_REQUEST_SCHEMA_VERSION}),
    "generation_response": frozenset({GENERATION_RESPONSE_SCHEMA_VERSION}),
    "structured_output_spec": frozenset({STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION}),
    "tool_schema": frozenset({TOOL_SCHEMA_SCHEMA_VERSION}),
    "provider_capabilities": frozenset({PROVIDER_CAPABILITIES_SCHEMA_VERSION}),
    "model_config": frozenset({MODEL_CONFIG_SCHEMA_VERSION}),
    "provider_usage": frozenset({PROVIDER_USAGE_SCHEMA_VERSION}),
    "provider_error": frozenset({PROVIDER_ERROR_SCHEMA_VERSION}),
    "recorded_response_key": frozenset({RECORDED_RESPONSE_KEY_SCHEMA_VERSION}),
    "generation_artifact": frozenset({GENERATION_ARTIFACT_SCHEMA_VERSION}),
    "provider_generate_request": frozenset({PROVIDER_GENERATE_REQUEST_SCHEMA_VERSION}),
    "provider_generate_response": frozenset({PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION}),
    "agent_definition": frozenset({AGENT_DEFINITION_SCHEMA_VERSION}),
    "agent_task": frozenset({AGENT_TASK_SCHEMA_VERSION}),
    "agent_state_transition": frozenset({AGENT_STATE_TRANSITION_SCHEMA_VERSION}),
    "tool_definition": frozenset({TOOL_DEFINITION_SCHEMA_VERSION}),
    "tool_invocation": frozenset({TOOL_INVOCATION_SCHEMA_VERSION}),
    "tool_result": frozenset({TOOL_RESULT_SCHEMA_VERSION}),
    "evidence_citation": frozenset({EVIDENCE_CITATION_SCHEMA_VERSION}),
    "agent_budget": frozenset({AGENT_BUDGET_SCHEMA_VERSION}),
    "agent_artifact": frozenset({AGENT_ARTIFACT_SCHEMA_VERSION}),
    "create_agent_session_request": frozenset({CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION}),
    "create_agent_task_request": frozenset({CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION}),
    "agent_session_detail": frozenset({AGENT_SESSION_DETAIL_SCHEMA_VERSION}),
    "watchtower_triage_result": frozenset({WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION}),
    "trace_investigation_plan": frozenset({TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION}),
    "evidence_attachment": frozenset({EVIDENCE_ATTACHMENT_SCHEMA_VERSION}),
    "candidate_affected_asset": frozenset({CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION}),
    "investigation_note": frozenset({INVESTIGATION_NOTE_SCHEMA_VERSION}),
    "agent_graph_overlay": frozenset({AGENT_GRAPH_OVERLAY_SCHEMA_VERSION}),
    "investigation_detail": frozenset({1, 2, 3, INVESTIGATION_DETAIL_SCHEMA_VERSION}),
    "stale_proposal_error": frozenset({STALE_PROPOSAL_ERROR_SCHEMA_VERSION}),
    "proposal_modification": frozenset({PROPOSAL_MODIFICATION_SCHEMA_VERSION}),
    "final_policy_check": frozenset({FINAL_POLICY_CHECK_SCHEMA_VERSION}),
    "authorized_simulation_command": frozenset({AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION}),
    "execution_result": frozenset({EXECUTION_RESULT_SCHEMA_VERSION}),
    "approve_proposal_request": frozenset({APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION}),
    "reject_proposal_request": frozenset({REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION}),
    "modify_proposal_request": frozenset({MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION}),
    "cancel_proposal_request": frozenset({CANCEL_PROPOSAL_REQUEST_SCHEMA_VERSION}),
    "approve_proposal_response": frozenset({APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION}),
    "reject_proposal_response": frozenset({REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION}),
    "modify_proposal_response": frozenset({MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION}),
    "trigger_watchtower_request": frozenset({TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION}),
}


def assert_supported_schema_version(
    contract_name: str,
    schema_version: int,
    *,
    trace_id: str | None = None,
) -> None:
    supported = SUPPORTED_SCHEMA_VERSIONS.get(contract_name)
    if supported is None:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message=f"Unknown contract name: {contract_name}",
            details={"contractName": contract_name},
            trace_id=trace_id,
        )
    if schema_version not in supported:
        raise ContractValidationError(
            code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
            message=(
                f"Unsupported schema version {schema_version} for contract {contract_name}"
            ),
            details={
                "contractName": contract_name,
                "schemaVersion": schema_version,
                "supportedVersions": sorted(supported),
            },
            trace_id=trace_id,
        )
