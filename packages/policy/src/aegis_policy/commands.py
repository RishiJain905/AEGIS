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
