"""Phase 22 proposal tool definitions."""

from __future__ import annotations

from aegis_contracts.agent_runtime import AgentToolClass, ToolDefinitionV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import TOOL_DEFINITION_SCHEMA_VERSION

PROPOSAL_TOOL_DEFINITIONS: list[ToolDefinitionV1] = [
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="list_proposals",
        description="List action proposals and revisions for the incident.",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "proposals": {"type": "array"},
                "revisions": {"type": "array"},
                "policyDecisions": {"type": "array"},
            },
        },
        allowed_roles=[AgentRole.WARDEN, AgentRole.BASTION],
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="create_response_proposal",
        description=(
            "Create an evidence-grounded response proposal with allowlisted scenario command."
        ),
        tool_class=AgentToolClass.PROPOSAL,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "selectedOptionId": {"type": "string"},
                "rationale": {"type": "string"},
                "riskTradeoffs": {"type": "string"},
                "linkedHypothesisIds": {"type": "array", "items": {"type": "string"}},
                "responseOptions": {"type": "array"},
            },
            "required": ["selectedOptionId", "rationale", "riskTradeoffs", "responseOptions"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "proposalId": {"type": "string"},
                "revisionId": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["proposalId", "revisionId", "status"],
        },
        allowed_roles=[AgentRole.BASTION],
    ),
]
