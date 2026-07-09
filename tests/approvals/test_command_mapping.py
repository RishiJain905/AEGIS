"""Unit tests for Phase 24 authorized command mapping."""

from __future__ import annotations

import pytest
from aegis_api.commands.mapping import map_scenario_command_to_authorized
from aegis_contracts.proposals import ScenarioCommandTemplateV1


def test_isolate_maps_to_set_asset_status() -> None:
    command = map_scenario_command_to_authorized(
        proposal_id="prp_01ARZ3NDEKTSV4RRFFQ69G5FAY",
        approval_id="apr_01ARZ3NDEKTSV4RRFFQ69G5FAZ",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        scenario_command=ScenarioCommandTemplateV1.ISOLATE,
        target_asset_id="asset:svc-api-gateway",
        command_id="idem_approve_001",
    )
    assert command.plugin_id == "effect.set_asset_status"
    assert command.config["status"] == "isolated"
    assert command.config["assetId"] == "asset:svc-api-gateway"
    assert command.authorization_token == "synthetic-operator-token"


@pytest.mark.parametrize(
    ("template", "status"),
    [
        (ScenarioCommandTemplateV1.OBSERVE, "observed"),
        (ScenarioCommandTemplateV1.INCREASE_MONITORING, "heightened_monitoring"),
        (ScenarioCommandTemplateV1.RESTRICT_ACCESS, "access_restricted"),
        (ScenarioCommandTemplateV1.REVOKE_CREDENTIALS, "credentials_revoked"),
        (ScenarioCommandTemplateV1.RESTART_SERVICE, "restarting"),
        (ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT, "rolling_back"),
    ],
)
def test_all_allowlisted_commands_map(template: ScenarioCommandTemplateV1, status: str) -> None:
    command = map_scenario_command_to_authorized(
        proposal_id="prp_01ARZ3NDEKTSV4RRFFQ69G5FAY",
        approval_id="apr_01ARZ3NDEKTSV4RRFFQ69G5FAZ",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        scenario_command=template,
        target_asset_id="asset:svc-api-gateway",
        command_id=f"idem_{template.value}",
    )
    assert command.config["status"] == status
    assert command.scenario_command == template
