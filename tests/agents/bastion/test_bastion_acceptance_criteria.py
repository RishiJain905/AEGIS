"""Phase 22 BASTION acceptance criteria tests."""

from __future__ import annotations

from aegis_agents.roles.bastion.schemas import BASTION_PROPOSAL_OUTPUT_SCHEMA
from aegis_agents.roles.registry import get_role_handler
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.entities import AgentRole


def test_bastion_handler_registered_with_phase22_prompt() -> None:
    handler = get_role_handler(AgentRole.BASTION)
    assert handler is not None
    assert handler.prompt_version == "phase22-bastion-v1"


def test_bastion_output_schema_requires_response_options() -> None:
    assert BASTION_PROPOSAL_OUTPUT_SCHEMA["properties"]["responseOptions"]["minItems"] >= 1


def test_bastion_cannot_use_hypothesis_mutation_tools() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.BASTION)
    try:
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="create_hypothesis_revision",
        )
        raised = False
    except AgentRuntimeError:
        raised = True
    assert raised


def test_oracle_cannot_create_response_proposal() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.ORACLE)
    try:
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="create_response_proposal",
        )
        raised = False
    except AgentRuntimeError:
        raised = True
    assert raised
