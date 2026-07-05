"""JSON schemas for Phase 22 BASTION structured outputs."""

from __future__ import annotations

from typing import Any

from aegis_agents.roles.common.schemas import _EVIDENCE_CITATION_SCHEMA, _TOOL_REQUEST_SCHEMA

_RESPONSE_OPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "optionId": {"type": "string", "minLength": 1, "maxLength": 64},
        "scenarioCommand": {
            "type": "string",
            "enum": [
                "observe",
                "increase_monitoring",
                "isolate",
                "revoke_credentials",
                "restrict_access",
                "restart_service",
                "rollback_deployment",
            ],
        },
        "targetAssetId": {"type": "string", "minLength": 1},
        "affectedAssetIds": {"type": "array", "items": {"type": "string"}},
        "evidenceIds": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "hypothesisIds": {"type": "array", "items": {"type": "string"}},
        "expectedBenefit": {"type": "string", "minLength": 1, "maxLength": 2048},
        "operationalCost": {"type": "string", "minLength": 1, "maxLength": 2048},
        "reversibility": {"type": "string", "minLength": 1, "maxLength": 1024},
        "prerequisites": {"type": "array", "items": {"type": "string"}},
        "monitoringPlan": {"type": "string", "minLength": 1, "maxLength": 2048},
        "expectedConsequences": {"type": "string", "minLength": 1, "maxLength": 2048},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty": {"type": "string", "minLength": 1, "maxLength": 1024},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2048},
    },
    "required": [
        "optionId",
        "scenarioCommand",
        "targetAssetId",
        "evidenceIds",
        "expectedBenefit",
        "operationalCost",
        "reversibility",
        "monitoringPlan",
        "expectedConsequences",
        "confidence",
        "uncertainty",
        "rationale",
    ],
    "additionalProperties": False,
}

BASTION_PROPOSAL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string", "minLength": 1, "maxLength": 4096},
        "riskTradeoffs": {"type": "string", "minLength": 1, "maxLength": 4096},
        "linkedHypothesisIds": {"type": "array", "items": {"type": "string"}},
        "selectedOptionId": {"type": "string", "minLength": 1, "maxLength": 64},
        "responseOptions": {
            "type": "array",
            "items": _RESPONSE_OPTION_SCHEMA,
            "minItems": 1,
            "maxItems": 3,
        },
        "evidenceCitations": {"type": "array", "items": _EVIDENCE_CITATION_SCHEMA},
        "toolRequests": {"type": "array", "items": _TOOL_REQUEST_SCHEMA},
    },
    "required": ["rationale", "riskTradeoffs", "selectedOptionId", "responseOptions"],
    "additionalProperties": False,
}

WARDEN_POLICY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explanationProse": {"type": "string", "maxLength": 4096},
        "proposalIds": {"type": "array", "items": {"type": "string"}},
        "evidenceCitations": {"type": "array", "items": _EVIDENCE_CITATION_SCHEMA},
        "toolRequests": {"type": "array", "items": _TOOL_REQUEST_SCHEMA},
    },
    "required": ["explanationProse"],
    "additionalProperties": False,
}
