"""Allowlisted scenario command templates and action-class mapping."""

from __future__ import annotations

from aegis_contracts.entities import ActionClass
from aegis_contracts.proposals import ScenarioCommandTemplateV1

ALLOWLISTED_COMMANDS: frozenset[ScenarioCommandTemplateV1] = frozenset(ScenarioCommandTemplateV1)

COMMAND_TO_ACTION_CLASS: dict[ScenarioCommandTemplateV1, ActionClass] = {
    ScenarioCommandTemplateV1.OBSERVE: ActionClass.READ_ONLY,
    ScenarioCommandTemplateV1.INCREASE_MONITORING: ActionClass.LOW_IMPACT,
    ScenarioCommandTemplateV1.ISOLATE: ActionClass.OPERATIONAL,
    ScenarioCommandTemplateV1.RESTRICT_ACCESS: ActionClass.OPERATIONAL,
    ScenarioCommandTemplateV1.REVOKE_CREDENTIALS: ActionClass.OPERATIONAL,
    ScenarioCommandTemplateV1.RESTART_SERVICE: ActionClass.CRITICAL,
    ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT: ActionClass.CRITICAL,
}

# The asset status each allowlisted command drives an asset into when executed via the
# ``effect.set_asset_status`` plugin. Single source of truth shared by the approval command
# mapping (apps/api) and the ghost-branch counterfactual engine (services/simulation), both
# of which must translate a scenario command into the same deterministic world mutation.
# Statuses are unique per command, so the mapping is invertible.
COMMAND_STATUS_MAP: dict[ScenarioCommandTemplateV1, str] = {
    ScenarioCommandTemplateV1.OBSERVE: "observed",
    ScenarioCommandTemplateV1.INCREASE_MONITORING: "heightened_monitoring",
    ScenarioCommandTemplateV1.ISOLATE: "isolated",
    ScenarioCommandTemplateV1.RESTRICT_ACCESS: "access_restricted",
    ScenarioCommandTemplateV1.REVOKE_CREDENTIALS: "credentials_revoked",
    ScenarioCommandTemplateV1.RESTART_SERVICE: "restarting",
    ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT: "rolling_back",
}

# Reverse lookup: which command produced a given operator/agent-set status. Used by the
# ghost engine to label a real executed decision reconstructed from the event stream.
STATUS_TO_COMMAND: dict[str, ScenarioCommandTemplateV1] = {
    status: command for command, status in COMMAND_STATUS_MAP.items()
}

CRITICALITY_BLOCK_THRESHOLD = 0.9
SCENARIO_RESTRICTED_COMMANDS: frozenset[ScenarioCommandTemplateV1] = frozenset(
    {
        ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT,
        ScenarioCommandTemplateV1.RESTART_SERVICE,
    }
)


def parse_command(command: str) -> ScenarioCommandTemplateV1 | None:
    try:
        return ScenarioCommandTemplateV1(command)
    except ValueError:
        return None


def expected_action_class(command: ScenarioCommandTemplateV1) -> ActionClass:
    return COMMAND_TO_ACTION_CLASS[command]
