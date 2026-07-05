"""JSON schemas for Phase 20 role structured outputs."""

from __future__ import annotations

from typing import Any

_CORRELATION_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alertIds": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "decision": {"type": "string", "minLength": 1, "maxLength": 32},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
        "factors": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["alertIds", "decision", "rationale"],
    "additionalProperties": False,
}

_ALERT_SUMMARY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alertId": {"type": "string"},
        "title": {"type": "string"},
        "severity": {"type": "string"},
        "assetId": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["alertId", "title", "severity", "assetId", "summary"],
    "additionalProperties": False,
}

_EVIDENCE_CITATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "evidenceId": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["evidenceId"],
    "additionalProperties": False,
}

_TOOL_REQUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "arguments": {"type": "object"},
        "purpose": {"type": "string"},
    },
    "required": ["name", "arguments"],
    "additionalProperties": False,
}

WATCHTOWER_TRIAGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alertSummaries": {
            "type": "array",
            "items": _ALERT_SUMMARY_OUTPUT_SCHEMA,
        },
        "groupedAlertIds": {
            "type": "array",
            "items": {"type": "string"},
        },
        "separatedAlertIds": {
            "type": "array",
            "items": {"type": "string"},
        },
        "correlationDecisions": {
            "type": "array",
            "items": _CORRELATION_DECISION_SCHEMA,
        },
        "escalation": {
            "type": "string",
            "enum": ["monitor", "investigate", "urgent"],
        },
        "escalationRationale": {"type": "string", "minLength": 1, "maxLength": 2048},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidenceCitations": {
            "type": "array",
            "items": _EVIDENCE_CITATION_SCHEMA,
        },
        "toolRequests": {
            "type": "array",
            "items": _TOOL_REQUEST_SCHEMA,
        },
    },
    "required": [
        "alertSummaries",
        "groupedAlertIds",
        "separatedAlertIds",
        "correlationDecisions",
        "escalation",
        "escalationRationale",
        "confidence",
        "evidenceCitations",
        "toolRequests",
    ],
    "additionalProperties": False,
}

_TRACE_SEARCH_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "toolName": {"type": "string", "minLength": 1, "maxLength": 128},
        "arguments": {"type": "object"},
        "purpose": {"type": "string", "minLength": 1, "maxLength": 512},
    },
    "required": ["toolName", "arguments", "purpose"],
    "additionalProperties": False,
}

_CANDIDATE_ASSET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assetId": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidenceIds": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
    },
    "required": ["assetId", "confidence", "rationale"],
    "additionalProperties": False,
}

_EVIDENCE_ATTACHMENT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sourceType": {
            "type": "string",
            "enum": ["event", "alert", "asset", "risk_path", "existing_evidence"],
        },
        "sourceId": {"type": "string"},
        "summary": {"type": "string"},
        "evidenceId": {"type": "string"},
        "assetId": {"type": "string"},
        "isContradiction": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
        "collectedByTool": {"type": "string"},
        "collectedAtSequence": {"type": "integer", "minimum": 0},
    },
    "required": ["sourceType", "sourceId", "summary", "confidence", "rationale"],
    "additionalProperties": False,
}

_GRAPH_HIGHLIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entityId": {"type": "string"},
        "entityType": {"type": "string"},
        "highlightKind": {"type": "string"},
        "label": {"type": "string"},
    },
    "required": ["entityId"],
    "additionalProperties": False,
}

TRACE_STEP_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidenceCitations": {
            "type": "array",
            "items": _EVIDENCE_CITATION_SCHEMA,
        },
        "toolRequests": {
            "type": "array",
            "items": _TOOL_REQUEST_SCHEMA,
        },
        "seedAssetIds": {
            "type": "array",
            "items": {"type": "string"},
        },
        "timeWindowStartSequence": {"type": ["integer", "null"], "minimum": 0},
        "timeWindowEndSequence": {"type": ["integer", "null"], "minimum": 0},
        "maxHops": {"type": "integer", "minimum": 1, "maximum": 8},
        "maxToolCalls": {"type": "integer", "minimum": 1, "maximum": 50},
        "searchSteps": {
            "type": "array",
            "items": _TRACE_SEARCH_STEP_SCHEMA,
        },
        "candidateAssets": {
            "type": "array",
            "items": _CANDIDATE_ASSET_SCHEMA,
        },
        "evidenceAttachments": {
            "type": "array",
            "items": _EVIDENCE_ATTACHMENT_OUTPUT_SCHEMA,
        },
        "graphHighlights": {
            "type": "array",
            "items": _GRAPH_HIGHLIGHT_SCHEMA,
        },
        "edgeHighlights": {
            "type": "array",
            "items": _GRAPH_HIGHLIGHT_SCHEMA,
        },
        "overlayRationale": {"type": "string", "minLength": 1, "maxLength": 2048},
    },
    "required": [
        "rationale",
        "confidence",
        "evidenceCitations",
        "toolRequests",
        "seedAssetIds",
        "maxHops",
        "maxToolCalls",
        "searchSteps",
    ],
    "additionalProperties": False,
}
