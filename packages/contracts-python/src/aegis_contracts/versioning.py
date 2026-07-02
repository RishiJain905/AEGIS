"""Schema and protocol version constants for AEGIS shared contracts."""

from __future__ import annotations

from typing import Final

from aegis_contracts.errors import ContractErrorCode, ContractValidationError

WORKSPACE_VERSION: Final[str] = "0.0.0-phase14"

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
HYPOTHESIS_SCHEMA_VERSION: Final[int] = 1
AGENT_SESSION_SCHEMA_VERSION: Final[int] = 1
ACTION_PROPOSAL_SCHEMA_VERSION: Final[int] = 1
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
    "hypothesis": frozenset({HYPOTHESIS_SCHEMA_VERSION}),
    "agent_session": frozenset({AGENT_SESSION_SCHEMA_VERSION}),
    "action_proposal": frozenset({ACTION_PROPOSAL_SCHEMA_VERSION}),
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
