"""ORACLE hypothesis tool definitions."""

from __future__ import annotations

from aegis_contracts.agent_runtime import AgentToolClass, ToolDefinitionV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import TOOL_DEFINITION_SCHEMA_VERSION

HYPOTHESIS_TOOL_DEFINITIONS: list[ToolDefinitionV1] = [
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="list_hypotheses",
        description="List hypotheses and current revisions for the incident.",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "hypotheses": {"type": "array"},
                "revisions": {"type": "array"},
            },
        },
        allowed_roles=[AgentRole.ORACLE],
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="create_hypothesis_revision",
        description="Append an evidence-grounded hypothesis revision.",
        tool_class=AgentToolClass.ANALYSIS_WRITE,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "hypothesisId": {"type": "string"},
                "family": {"type": "string"},
                "claim": {"type": "string"},
                "confidence": {"type": "object"},
                "claims": {"type": "array"},
                "supportingEvidenceIds": {"type": "array", "items": {"type": "string"}},
                "contradictingEvidenceIds": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "unknowns": {"type": "array", "items": {"type": "string"}},
                "predictions": {"type": "array", "items": {"type": "string"}},
                "contradictionLinks": {"type": "array"},
            },
            "required": ["family", "claim", "confidence", "supportingEvidenceIds"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "hypothesisId": {"type": "string"},
                "revisionId": {"type": "string"},
                "rejectedClaims": {"type": "array"},
                "downgradedClaims": {"type": "array"},
            },
        },
        allowed_roles=[AgentRole.ORACLE],
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="request_trace_verification",
        description="Request bounded TRACE verification for a hypothesis.",
        tool_class=AgentToolClass.ANALYSIS_WRITE,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "hypothesisId": {"type": "string"},
                "purpose": {"type": "string"},
                "targetEvidenceIds": {"type": "array", "items": {"type": "string"}},
                "idempotencyKey": {"type": "string"},
            },
            "required": ["hypothesisId", "purpose", "idempotencyKey"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "verificationId": {"type": "string"},
                "replayed": {"type": "boolean"},
            },
        },
        allowed_roles=[AgentRole.ORACLE],
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="retire_hypothesis",
        description="Retire a hypothesis via append-only revision.",
        tool_class=AgentToolClass.ANALYSIS_WRITE,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "hypothesisId": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["hypothesisId", "rationale"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "hypothesisId": {"type": "string"},
                "revisionId": {"type": "string"},
            },
        },
        allowed_roles=[AgentRole.ORACLE],
    ),
]
