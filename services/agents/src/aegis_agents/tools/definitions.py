"""Canonical tool definitions for Phase 19 generic runtime."""

from __future__ import annotations

from aegis_agents.tools.hypothesis import HYPOTHESIS_TOOL_DEFINITIONS
from aegis_agents.tools.investigation import INVESTIGATION_TOOL_DEFINITIONS
from aegis_contracts.agent_runtime import AgentToolClass, ToolDefinitionV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import TOOL_DEFINITION_SCHEMA_VERSION

_ALL_ROLES = list(AgentRole)

CANONICAL_TOOL_DEFINITIONS: list[ToolDefinitionV1] = [
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="list_evidence",
        description="List evidence visible for the incident run",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "evidenceIds": {"type": "array", "items": {"type": "string"}},
                "summaries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["id", "summary"],
                    },
                },
            },
            "required": ["evidenceIds", "summaries"],
        },
        allowed_roles=_ALL_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_incident",
        description="Return incident metadata for the active investigation",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "incidentId": {"type": "string"},
                "runId": {"type": "string"},
                "state": {"type": "string"},
            },
            "required": ["incidentId", "runId", "state"],
        },
        allowed_roles=_ALL_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="create_hypothesis",
        description="Persist an analysis hypothesis with grounded evidence citations",
        tool_class=AgentToolClass.ANALYSIS_WRITE,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "statement": {"type": "string", "minLength": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidenceIds": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "required": ["statement", "confidence", "evidenceIds"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "hypothesisId": {"type": "string"},
                "artifactId": {"type": "string"},
            },
            "required": ["hypothesisId", "artifactId"],
        },
        allowed_roles=_ALL_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="create_action_proposal",
        description="Create a pending action proposal without executing simulator changes",
        tool_class=AgentToolClass.PROPOSAL,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "targetAssetId": {"type": "string"},
                "command": {"type": "string", "minLength": 1},
                "actionClass": {
                    "type": "string",
                    "enum": ["class_0", "class_1", "class_2", "class_3"],
                },
                "rationale": {"type": "string"},
                "evidenceIds": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "required": ["targetAssetId", "command", "actionClass", "evidenceIds"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "proposalId": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["proposalId", "status"],
        },
        allowed_roles=[AgentRole.BASTION, AgentRole.WARDEN, AgentRole.TRACE],
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="execute_simulation_command",
        description="Internal execution adapter — not model visible",
        tool_class=AgentToolClass.EXECUTION,
        model_visible=False,
        input_schema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
        output_schema={"type": "object", "properties": {"executed": {"type": "boolean"}}},
        allowed_roles=[],
    ),
    *INVESTIGATION_TOOL_DEFINITIONS,
    *HYPOTHESIS_TOOL_DEFINITIONS,
]
