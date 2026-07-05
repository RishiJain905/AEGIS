"""JSON schemas for Phase 21 ORACLE structured outputs."""

from __future__ import annotations

from typing import Any

from aegis_agents.roles.common.schemas import _EVIDENCE_CITATION_SCHEMA, _TOOL_REQUEST_SCHEMA

_CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": [
                "observed_fact",
                "model_score",
                "graph_risk",
                "agent_inference",
                "unsupported_claim",
            ],
        },
        "text": {"type": "string", "minLength": 1, "maxLength": 2048},
        "evidenceIds": {"type": "array", "items": {"type": "string"}},
        "attachmentIds": {"type": "array", "items": {"type": "string"}},
        "isAssumption": {"type": "boolean"},
    },
    "required": ["kind", "text"],
    "additionalProperties": False,
}

_CONFIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "point": {"type": "number", "minimum": 0, "maximum": 1},
        "min": {"type": "number", "minimum": 0, "maximum": 1},
        "max": {"type": "number", "minimum": 0, "maximum": 1},
        "coverage": {"type": "number", "minimum": 0, "maximum": 1},
        "contradictionPenalty": {"type": "number", "minimum": 0, "maximum": 1},
        "explanation": {"type": "string", "minLength": 1, "maxLength": 2048},
    },
    "required": ["point", "min", "max", "coverage", "contradictionPenalty", "explanation"],
    "additionalProperties": False,
}

_CONTRADICTION_LINK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "supportingEvidenceIds": {"type": "array", "items": {"type": "string"}},
        "contradictingEvidenceIds": {"type": "array", "items": {"type": "string"}},
        "supportingAttachmentIds": {"type": "array", "items": {"type": "string"}},
        "contradictingAttachmentIds": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
    },
    "required": ["rationale"],
    "additionalProperties": False,
}

_HYPOTHESIS_OUTPUT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "family": {
            "type": "string",
            "enum": [
                "lateral_movement",
                "credential_abuse",
                "benign_anomaly",
                "supply_chain",
                "insider_threat",
                "data_exfiltration",
            ],
        },
        "claim": {"type": "string", "minLength": 1, "maxLength": 4096},
        "confidence": _CONFIDENCE_SCHEMA,
        "claims": {"type": "array", "items": _CLAIM_SCHEMA},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "supportingEvidenceIds": {"type": "array", "items": {"type": "string"}},
        "contradictingEvidenceIds": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "predictions": {"type": "array", "items": {"type": "string"}},
        "contradictionLinks": {"type": "array", "items": _CONTRADICTION_LINK_SCHEMA},
        "existingHypothesisId": {"type": "string"},
    },
    "required": ["family", "claim", "confidence", "supportingEvidenceIds"],
    "additionalProperties": False,
}

_VERIFICATION_REQUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hypothesisIndex": {"type": "integer", "minimum": 0},
        "purpose": {"type": "string", "minLength": 1, "maxLength": 2048},
        "targetEvidenceIds": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["purpose"],
    "additionalProperties": False,
}

ORACLE_HYPOTHESIS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hypotheses": {
            "type": "array",
            "items": _HYPOTHESIS_OUTPUT_ITEM_SCHEMA,
            "minItems": 2,
        },
        "comparisonSummary": {"type": "string", "minLength": 1, "maxLength": 4096},
        "verificationRequests": {
            "type": "array",
            "items": _VERIFICATION_REQUEST_SCHEMA,
        },
        "evidenceCitations": {
            "type": "array",
            "items": _EVIDENCE_CITATION_SCHEMA,
        },
        "toolRequests": {
            "type": "array",
            "items": _TOOL_REQUEST_SCHEMA,
        },
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
    },
    "required": ["hypotheses", "comparisonSummary", "rationale"],
    "additionalProperties": False,
}
