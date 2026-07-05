"""Proposal revision builders for BASTION."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import ActionProposalV1
from aegis_contracts.entities import ProposalStatus
from aegis_contracts.proposals import (
    ProposalRevisionV1,
    ResponseOptionV1,
    ScenarioCommandTemplateV1,
)
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    PROPOSAL_REVISION_SCHEMA_VERSION,
    RESPONSE_OPTION_SCHEMA_VERSION,
)
from aegis_policy.commands import COMMAND_TO_ACTION_CLASS


def build_response_option(structured: dict[str, Any]) -> ResponseOptionV1:
    command = ScenarioCommandTemplateV1(structured["scenarioCommand"])
    return ResponseOptionV1(
        schema_version=RESPONSE_OPTION_SCHEMA_VERSION,
        option_id=structured["optionId"],
        scenario_command=command,
        action_class=COMMAND_TO_ACTION_CLASS[command],
        target_asset_id=structured["targetAssetId"],
        affected_asset_ids=structured.get("affectedAssetIds", []),
        evidence_ids=structured["evidenceIds"],
        hypothesis_ids=structured.get("hypothesisIds", []),
        expected_benefit=structured["expectedBenefit"],
        operational_cost=structured["operationalCost"],
        reversibility=structured["reversibility"],
        prerequisites=structured.get("prerequisites", []),
        monitoring_plan=structured["monitoringPlan"],
        expected_consequences=structured["expectedConsequences"],
        confidence=structured["confidence"],
        uncertainty=structured["uncertainty"],
        rationale=structured["rationale"],
    )


def build_proposal_bundle(
    *,
    incident_id: str,
    session_id: str,
    task_id: str,
    structured: dict[str, Any],
    response_options: list[ResponseOptionV1],
) -> tuple[ActionProposalV1, ProposalRevisionV1]:
    now = datetime.now(UTC)
    proposal_id = new_runtime_id("prp")
    revision_id = new_runtime_id("prv")
    selected = next(
        option for option in response_options if option.option_id == structured["selectedOptionId"]
    )
    revision = ProposalRevisionV1(
        schema_version=PROPOSAL_REVISION_SCHEMA_VERSION,
        id=revision_id,
        proposal_id=proposal_id,
        incident_id=incident_id,
        session_id=session_id,
        task_id=task_id,
        revision_number=1,
        response_options=response_options,
        selected_option_id=structured["selectedOptionId"],
        rationale=structured["rationale"],
        risk_tradeoffs=structured["riskTradeoffs"],
        linked_hypothesis_ids=structured.get("linkedHypothesisIds", []),
        created_at=now,
    )
    proposal = ActionProposalV1(
        schema_version=ACTION_PROPOSAL_SCHEMA_VERSION,
        id=proposal_id,
        incident_id=incident_id,
        agent_session_id=session_id,
        action_class=selected.action_class,
        target_asset_id=selected.target_asset_id,
        command=selected.scenario_command.value,
        scenario_command=selected.scenario_command.value,
        current_revision_id=revision_id,
        status=ProposalStatus.PENDING,
        rationale=structured["rationale"],
        revision=1,
        created_at=now,
    )
    return proposal, revision
