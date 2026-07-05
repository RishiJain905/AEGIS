"""WARDEN policy input builders."""

from __future__ import annotations

from aegis_contracts import ActionProposalV1
from aegis_contracts.entities import AgentRole, IncidentState
from aegis_contracts.proposals import PolicyInputV1, ProposalRevisionV1
from aegis_contracts.versioning import POLICY_INPUT_SCHEMA_VERSION


def build_policy_input(
    *,
    proposal: ActionProposalV1,
    revision: ProposalRevisionV1,
    incident_state: IncidentState,
    asset_criticality: float,
    scenario_restricted: bool = True,
    hypothesis_confidence_min: float | None = None,
) -> PolicyInputV1:
    selected = next(
        option
        for option in revision.response_options
        if option.option_id == revision.selected_option_id
    )
    return PolicyInputV1(
        schema_version=POLICY_INPUT_SCHEMA_VERSION,
        proposal_id=proposal.id,
        proposal_revision_id=revision.id,
        proposal_revision_number=revision.revision_number,
        current_revision_id=proposal.current_revision_id or revision.id,
        action_class=selected.action_class,
        scenario_command=selected.scenario_command,
        agent_role=AgentRole.BASTION,
        target_asset_id=selected.target_asset_id,
        asset_criticality=asset_criticality,
        reversibility=selected.reversibility,
        incident_state=incident_state,
        scenario_restricted=scenario_restricted,
        hypothesis_confidence_min=hypothesis_confidence_min,
    )
