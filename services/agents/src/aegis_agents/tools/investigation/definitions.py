"""Phase 20 investigation tool definitions."""

from __future__ import annotations

from aegis_contracts.agent_runtime import AgentToolClass, ToolDefinitionV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import TOOL_DEFINITION_SCHEMA_VERSION

_INVESTIGATION_ROLES = [AgentRole.WATCHTOWER, AgentRole.TRACE]
_ORACLE_READ_ROLES = [AgentRole.WATCHTOWER, AgentRole.TRACE, AgentRole.ORACLE]

_EVENT_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "eventId": {"type": "string"},
        "sequence": {"type": "integer", "minimum": 0},
        "type": {"type": "string"},
        "simTime": {"type": "string"},
        "payload": {"type": "object"},
    },
    "required": ["eventId", "sequence", "type", "simTime"],
}

_ASSET_SCHEMA = {
    "type": "object",
    "properties": {
        "assetId": {"type": "string"},
        "label": {"type": "string"},
        "assetType": {"type": "string"},
        "status": {"type": "string"},
        "riskScore": {"type": "number", "minimum": 0, "maximum": 1},
        "criticality": {"type": "number", "minimum": 0, "maximum": 1},
        "clusterId": {"type": ["string", "null"]},
    },
    "required": ["assetId", "label", "assetType", "status", "riskScore", "criticality"],
}

_EDGE_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "edgeId": {"type": "string"},
        "sourceId": {"type": "string"},
        "targetId": {"type": "string"},
        "relationshipType": {"type": "string"},
        "directed": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["edgeId", "sourceId", "targetId", "relationshipType", "directed", "confidence"],
}

_ALERT_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "alertId": {"type": "string"},
        "title": {"type": "string"},
        "severity": {"type": "string"},
        "assetId": {"type": "string"},
        "sourceEventId": {"type": "string"},
        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "createdAt": {"type": "string"},
    },
    "required": ["alertId", "title", "severity", "assetId", "sourceEventId", "createdAt"],
}

_RISK_SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "assetId": {"type": "string"},
        "total": {"type": "number", "minimum": 0, "maximum": 1},
        "direct": {"type": "number", "minimum": 0, "maximum": 1},
        "propagated": {"type": "number", "minimum": 0, "maximum": 1},
        "computedAtSequence": {"type": "integer", "minimum": 0},
    },
    "required": ["assetId", "total", "direct", "propagated", "computedAtSequence"],
}

_EVIDENCE_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "evidenceId": {"type": "string"},
        "summary": {"type": "string"},
        "assetId": {"type": ["string", "null"]},
        "sourceEventId": {"type": "string"},
    },
    "required": ["evidenceId", "summary", "sourceEventId"],
}

_PROVENANCE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "sourceType": {
            "type": "string",
            "enum": ["event", "alert", "asset", "risk_path", "existing_evidence"],
        },
        "sourceId": {"type": "string", "minLength": 1, "maxLength": 128},
        "summary": {"type": "string", "minLength": 1, "maxLength": 2048},
        "collectedByTool": {"type": "string", "maxLength": 128},
        "collectedAtSequence": {"type": "integer", "minimum": 0},
    },
    "required": ["sourceType", "sourceId", "summary"],
    "additionalProperties": False,
}

INVESTIGATION_TOOL_DEFINITIONS: list[ToolDefinitionV1] = [
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="search_events",
        description=(
            "Search normalized domain events for the active run by asset, event type, "
            "text, or sim-time window — the same search the operator's Evidence tab runs"
        ),
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "fromSequence": {"type": "integer", "minimum": 0},
                "toSequence": {"type": "integer", "minimum": 0},
                "assetId": {"type": "string", "minLength": 1},
                "eventTypePrefix": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "fromSimTime": {"type": "string"},
                "toSimTime": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 200},
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "events": {"type": "array", "items": _EVENT_SUMMARY_SCHEMA},
                "count": {"type": "integer", "minimum": 0},
                "fromSequence": {"type": ["integer", "null"], "minimum": 0},
                "toSequence": {"type": ["integer", "null"], "minimum": 0},
            },
            "required": ["events", "count"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_asset",
        description="Return operational graph metadata for a single asset from the latest snapshot",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {"assetId": {"type": "string", "minLength": 1}},
            "required": ["assetId"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "asset": _ASSET_SCHEMA,
                "snapshotSequence": {"type": "integer", "minimum": 0},
            },
            "required": ["asset", "snapshotSequence"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_relationships",
        description=(
            "Return bounded neighborhood relationships around an asset "
            "from the latest graph snapshot"
        ),
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "minLength": 1},
                "maxDegree": {"type": "integer", "minimum": 1, "maximum": 8, "default": 8},
                "relationshipTypes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "directedOnly": {"type": "boolean", "default": False},
            },
            "required": ["assetId"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "centerAssetId": {"type": "string"},
                "maxDegree": {"type": "integer", "minimum": 1, "maximum": 8},
                "assets": {"type": "array", "items": _ASSET_SCHEMA},
                "edges": {"type": "array", "items": _EDGE_SUMMARY_SCHEMA},
                "hopRings": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "explanation": {"type": "object"},
            },
            "required": [
                "centerAssetId",
                "maxDegree",
                "assets",
                "edges",
                "hopRings",
                "explanation",
            ],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_paths",
        description="Find bounded paths between two assets in the latest graph snapshot",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "sourceId": {"type": "string", "minLength": 1},
                "targetId": {"type": "string", "minLength": 1},
                "maxHops": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
                "relationshipTypes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "directedOnly": {"type": "boolean", "default": True},
            },
            "required": ["sourceId", "targetId"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "sourceId": {"type": "string"},
                "targetId": {"type": "string"},
                "paths": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "explanation": {"type": "object"},
            },
            "required": ["sourceId", "targetId", "paths", "explanation"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_risk_scores",
        description="List latest asset risk scores for the active run",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "assetIds": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "scores": {"type": "array", "items": _RISK_SCORE_SCHEMA},
            },
            "required": ["scores"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="list_alerts",
        description="List alerts for the active run",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "alerts": {"type": "array", "items": _ALERT_SUMMARY_SCHEMA},
            },
            "required": ["alerts"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_alert",
        description="Return a single alert by identifier",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {"alertId": {"type": "string", "minLength": 1}},
            "required": ["alertId"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"alert": _ALERT_SUMMARY_SCHEMA},
            "required": ["alert"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="list_existing_evidence",
        description="List evidence visible to the active investigation session",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "evidence": {"type": "array", "items": _EVIDENCE_SUMMARY_SCHEMA},
            },
            "required": ["evidence"],
        },
        allowed_roles=_ORACLE_READ_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="attach_evidence",
        description="Persist a grounded evidence attachment with validated source references",
        tool_class=AgentToolClass.ANALYSIS_WRITE,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "provenance": _PROVENANCE_INPUT_SCHEMA,
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
                "isContradiction": {"type": "boolean", "default": False},
                "assetId": {"type": "string"},
                "evidenceId": {"type": "string"},
            },
            "required": ["provenance", "confidence", "rationale"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "attachmentId": {"type": "string"},
            },
            "required": ["attachmentId"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="create_investigation_note",
        description="Persist an investigation note grounded in visible evidence",
        tool_class=AgentToolClass.ANALYSIS_WRITE,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "note": {"type": "string", "minLength": 1, "maxLength": 4096},
                "evidenceIds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
            },
            "required": ["note", "evidenceIds"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "noteId": {"type": "string"},
            },
            "required": ["noteId"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="list_relationships",
        description="Alias for bounded neighborhood relationships around an asset",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "minLength": 1},
                "maxDegree": {"type": "integer", "minimum": 1, "maximum": 8, "default": 8},
                "relationshipTypes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "directedOnly": {"type": "boolean", "default": False},
            },
            "required": ["assetId"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "centerAssetId": {"type": "string"},
                "maxDegree": {"type": "integer", "minimum": 1, "maximum": 8},
                "assets": {"type": "array", "items": _ASSET_SCHEMA},
                "edges": {"type": "array", "items": _EDGE_SUMMARY_SCHEMA},
                "hopRings": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "explanation": {"type": "object"},
            },
            "required": [
                "centerAssetId",
                "maxDegree",
                "assets",
                "edges",
                "hopRings",
                "explanation",
            ],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_graph_paths",
        description="Alias for bounded paths between two assets",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "sourceId": {"type": "string", "minLength": 1},
                "targetId": {"type": "string", "minLength": 1},
                "maxHops": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
                "relationshipTypes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "directedOnly": {"type": "boolean", "default": True},
            },
            "required": ["sourceId", "targetId"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "sourceId": {"type": "string"},
                "targetId": {"type": "string"},
                "paths": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "explanation": {"type": "object"},
            },
            "required": ["sourceId", "targetId", "paths", "explanation"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
    ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="get_incident_timeline",
        description="Return a bounded incident timeline from domain events",
        tool_class=AgentToolClass.READ,
        model_visible=True,
        input_schema={
            "type": "object",
            "properties": {
                "fromSequence": {"type": "integer", "minimum": 0},
                "toSequence": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sequence": {"type": "integer"},
                            "eventId": {"type": "string"},
                            "type": {"type": "string"},
                            "simTime": {"type": "string"},
                        },
                        "required": ["sequence", "eventId", "type", "simTime"],
                    },
                },
            },
            "required": ["entries"],
        },
        allowed_roles=_INVESTIGATION_ROLES,
    ),
]
