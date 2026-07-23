"""Map allowlisted scenario commands to internal simulator EXECUTE payloads."""

from __future__ import annotations

from aegis_contracts.approvals import AuthorizedSimulationCommandV1
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION
from aegis_policy.commands import COMMAND_STATUS_MAP  # shared single source of truth

__all__ = [
    "APPROVAL_IDEMPOTENCY_SCOPE",
    "COMMAND_STATUS_MAP",
    "DEFAULT_AUTHORIZATION_TOKEN",
    "DEFAULT_OPERATOR_ACTOR_ID",
    "map_scenario_command_to_authorized",
]

DEFAULT_OPERATOR_ACTOR_ID = "asset:operator-console"
DEFAULT_AUTHORIZATION_TOKEN = "synthetic-operator-token"
APPROVAL_IDEMPOTENCY_SCOPE = "approval-workflow"


def map_scenario_command_to_authorized(
    *,
    proposal_id: str,
    approval_id: str,
    run_id: str,
    scenario_command: ScenarioCommandTemplateV1,
    target_asset_id: str,
    command_id: str,
    actor_id: str = DEFAULT_OPERATOR_ACTOR_ID,
    authorization_token: str = DEFAULT_AUTHORIZATION_TOKEN,
) -> AuthorizedSimulationCommandV1:
    status = COMMAND_STATUS_MAP.get(scenario_command)
    if status is None:
        msg = f"Unsupported scenario command template: {scenario_command}"
        raise ValueError(msg)
    return AuthorizedSimulationCommandV1(
        schema_version=AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION,
        proposal_id=proposal_id,
        approval_id=approval_id,
        run_id=run_id,
        scenario_command=scenario_command,
        plugin_id="effect.set_asset_status",
        target_asset_id=target_asset_id,
        config={
            "assetId": target_asset_id,
            "status": status,
            "scenarioCommand": scenario_command.value,
            "proposalId": proposal_id,
            "approvalId": approval_id,
        },
        command_id=command_id,
        authorization_token=authorization_token,
        actor_id=actor_id,
    )
