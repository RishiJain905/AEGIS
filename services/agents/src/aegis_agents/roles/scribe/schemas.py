"""SCRIBE structured narrative output schema."""

from __future__ import annotations

from typing import Any

from aegis_agents.roles.common.schemas import _EVIDENCE_CITATION_SCHEMA

SCRIBE_NARRATIVE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executiveSummary": {"type": "string", "minLength": 1, "maxLength": 4096},
        "chronologySummary": {"type": "string", "minLength": 1, "maxLength": 4096},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claimId": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "observed_fact",
                            "persisted_event",
                            "detection_score",
                            "graph_risk",
                            "investigation_evidence",
                            "oracle_hypothesis",
                            "bastion_proposal",
                            "warden_policy_decision",
                            "human_decision",
                            "agent_inference",
                            "unsupported",
                            "uncertain",
                        ],
                    },
                    "text": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "uncertainty": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "event",
                                        "evidence",
                                        "hypothesis",
                                        "proposal",
                                        "policy_decision",
                                        "model_score",
                                        "agent_task",
                                        "agent_session",
                                        "alert",
                                        "asset",
                                    ],
                                },
                                "referenceId": {"type": "string"},
                                "label": {"type": "string"},
                                "sequence": {"type": "integer", "minimum": 0},
                                "rationale": {"type": "string"},
                            },
                            "required": ["kind", "referenceId", "label"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["category", "text", "citations"],
                "additionalProperties": False,
            },
        },
        "lessons": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidenceCitations": {
            "type": "array",
            "items": _EVIDENCE_CITATION_SCHEMA,
        },
        "toolRequests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                    "purpose": {"type": "string"},
                },
                "required": ["name", "arguments"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "executiveSummary",
        "chronologySummary",
        "claims",
        "rationale",
        "confidence",
        "evidenceCitations",
        "toolRequests",
    ],
    "additionalProperties": False,
}
