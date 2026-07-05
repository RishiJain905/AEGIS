"""ORM row to domain contract mappers."""

from __future__ import annotations

from aegis_contracts import (
    ActionProposalV1,
    AgentArtifactV1,
    AgentBudgetV1,
    AgentSessionV1,
    AgentStateTransitionV1,
    AgentTaskV1,
    AlertV1,
    ApprovalV1,
    AssetRiskScoreV1,
    DomainEventEnvelopeV1,
    EvidenceV1,
    ExecutedActionV1,
    GenerationArtifactV1,
    GraphSnapshotV1,
    HypothesisV1,
    IdempotencyRecordV1,
    IncidentV1,
    ModelManifestV1,
    ModelScoreV1,
    ObjectMetadataReferenceV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SimulationCheckpointV1,
    ToolInvocationV1,
    parse_contract,
)

from aegis_persistence.orm.tables import (
    ActionProposalRow,
    AgentArtifactRow,
    AgentSessionRow,
    AgentStateTransitionRow,
    AgentTaskRow,
    AlertRow,
    ApprovalRow,
    AssetRiskScoreRow,
    DomainEventRow,
    EvidenceRow,
    ExecutedActionRow,
    GenerationArtifactRow,
    GraphSnapshotRow,
    HypothesisRow,
    IdempotencyRecordRow,
    IncidentRow,
    ModelManifestRow,
    ModelScoreRow,
    RunRow,
    ScenarioRow,
    ScenarioVersionRow,
    SimulationCheckpointRow,
    StoredObjectRow,
    ToolInvocationRow,
)


def scenario_to_domain(row: ScenarioRow) -> ScenarioV1:
    return parse_contract(ScenarioV1, row.payload)


def scenario_version_to_domain(row: ScenarioVersionRow) -> ScenarioVersionV1:
    return parse_contract(ScenarioVersionV1, row.payload)


def run_to_domain(row: RunRow) -> RunV1:
    return parse_contract(RunV1, row.payload)


def checkpoint_to_domain(row: SimulationCheckpointRow) -> SimulationCheckpointV1:
    return parse_contract(SimulationCheckpointV1, row.payload)


def incident_to_domain(row: IncidentRow) -> IncidentV1:
    return parse_contract(IncidentV1, row.payload)


def alert_to_domain(row: AlertRow) -> AlertV1:
    return parse_contract(AlertV1, row.payload)


def evidence_to_domain(row: EvidenceRow) -> EvidenceV1:
    return parse_contract(EvidenceV1, row.payload)


def hypothesis_to_domain(row: HypothesisRow) -> HypothesisV1:
    return parse_contract(HypothesisV1, row.payload)


def agent_session_to_domain(row: AgentSessionRow) -> AgentSessionV1:
    return parse_contract(AgentSessionV1, row.payload)


def agent_task_to_domain(row: AgentTaskRow) -> AgentTaskV1:
    return parse_contract(AgentTaskV1, row.payload)


def agent_state_transition_to_domain(row: AgentStateTransitionRow) -> AgentStateTransitionV1:
    return parse_contract(AgentStateTransitionV1, row.payload)


def tool_invocation_to_domain(row: ToolInvocationRow) -> ToolInvocationV1:
    return parse_contract(ToolInvocationV1, row.payload)


def agent_artifact_to_domain(row: AgentArtifactRow) -> AgentArtifactV1:
    return parse_contract(AgentArtifactV1, row.payload)


def agent_budget_from_row(row: AgentSessionRow) -> AgentBudgetV1 | None:
    if row.budget is None:
        return None
    return parse_contract(AgentBudgetV1, row.budget)


def action_proposal_to_domain(row: ActionProposalRow) -> ActionProposalV1:
    return parse_contract(ActionProposalV1, row.payload)


def approval_to_domain(row: ApprovalRow) -> ApprovalV1:
    return parse_contract(ApprovalV1, row.payload)


def executed_action_to_domain(row: ExecutedActionRow) -> ExecutedActionV1:
    return parse_contract(ExecutedActionV1, row.payload)


def model_manifest_to_domain(row: ModelManifestRow) -> ModelManifestV1:
    return parse_contract(ModelManifestV1, row.payload)


def model_score_to_domain(row: ModelScoreRow) -> ModelScoreV1:
    return parse_contract(ModelScoreV1, row.payload)


def asset_risk_score_to_domain(row: AssetRiskScoreRow) -> AssetRiskScoreV1:
    return parse_contract(AssetRiskScoreV1, row.payload)


def event_to_domain(row: DomainEventRow) -> DomainEventEnvelopeV1:
    return parse_contract(DomainEventEnvelopeV1, row.envelope)


def graph_snapshot_to_domain(row: GraphSnapshotRow) -> GraphSnapshotV1:
    return parse_contract(GraphSnapshotV1, row.payload)


def idempotency_record_to_domain(row: IdempotencyRecordRow) -> IdempotencyRecordV1:
    return parse_contract(IdempotencyRecordV1, row.payload)


def object_metadata_to_domain(row: StoredObjectRow) -> ObjectMetadataReferenceV1:
    return parse_contract(ObjectMetadataReferenceV1, row.payload)


def domain_to_payload(model: object) -> dict[str, object]:
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        dumped = dump(mode="json", by_alias=True)
        return dict(dumped)
    msg = f"Unsupported model type: {type(model)!r}"
    raise TypeError(msg)


def event_to_outbox_payload(envelope: DomainEventEnvelopeV1) -> dict[str, object]:
    return {
        "eventId": envelope.event_id,
        "runId": envelope.run_id,
        "sequence": envelope.sequence,
        "type": envelope.type,
        "channel": "events",
    }


def generation_artifact_to_domain(row: GenerationArtifactRow) -> GenerationArtifactV1:
    return parse_contract(GenerationArtifactV1, row.payload)
