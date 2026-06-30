"""Fixture name to contract model mapping for cross-language tests."""

from __future__ import annotations

from pydantic import BaseModel

from aegis_contracts.api import CursorPaginationV1, IdempotencyMetadataV1
from aegis_contracts.entities import (
    ActionProposalV1,
    AgentSessionV1,
    AlertV1,
    ApprovalV1,
    EvidenceV1,
    ExecutedActionV1,
    HypothesisV1,
    IncidentV1,
    ModelManifestV1,
    ModelScoreV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
)
from aegis_contracts.errors import ApiErrorEnvelopeV1
from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.graph import (
    GraphDeltaV1,
    GraphEdgeV1,
    GraphNodeV1,
    GraphPathQueryV1,
    GraphPathResultV1,
    GraphSnapshotV1,
)

FIXTURE_MODEL_MAP: dict[str, type[BaseModel]] = {
    "event_envelope_v1": DomainEventEnvelopeV1,
    "graph_node_v1": GraphNodeV1,
    "graph_edge_v1": GraphEdgeV1,
    "graph_snapshot_v1": GraphSnapshotV1,
    "graph_delta_v1": GraphDeltaV1,
    "graph_path_query_v1": GraphPathQueryV1,
    "graph_path_result_v1": GraphPathResultV1,
    "api_error_v1": ApiErrorEnvelopeV1,
    "cursor_page_v1": CursorPaginationV1,
    "idempotency_v1": IdempotencyMetadataV1,
    "scenario_v1": ScenarioV1,
    "scenario_version_v1": ScenarioVersionV1,
    "run_v1": RunV1,
    "alert_v1": AlertV1,
    "incident_v1": IncidentV1,
    "evidence_v1": EvidenceV1,
    "hypothesis_v1": HypothesisV1,
    "agent_session_v1": AgentSessionV1,
    "action_proposal_v1": ActionProposalV1,
    "approval_v1": ApprovalV1,
    "executed_action_v1": ExecutedActionV1,
    "model_manifest_v1": ModelManifestV1,
    "model_score_v1": ModelScoreV1,
}
