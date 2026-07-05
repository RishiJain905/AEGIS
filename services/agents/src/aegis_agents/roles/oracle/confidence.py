"""Confidence assessment validation for ORACLE."""

from __future__ import annotations

from typing import Any

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.hypothesis import ConfidenceAssessmentV1
from aegis_contracts.versioning import CONFIDENCE_ASSESSMENT_SCHEMA_VERSION


def build_confidence_assessment(
    raw: dict[str, Any],
    *,
    supporting_count: int,
    contradicting_count: int,
    total_visible: int,
) -> ConfidenceAssessmentV1:
    point = float(raw.get("point", 0.5))
    min_value = float(raw.get("min", max(0.0, point - 0.15)))
    max_value = float(raw.get("max", min(1.0, point + 0.15)))
    coverage = float(raw.get("coverage", _coverage(supporting_count, total_visible)))
    contradiction_penalty = float(
        raw.get(
            "contradictionPenalty",
            min(1.0, contradicting_count * 0.15),
        )
    )
    explanation = str(
        raw.get(
            "explanation",
            "Confidence derived from grounded evidence coverage and contradiction penalty.",
        )
    )
    assessment = ConfidenceAssessmentV1(
        schema_version=CONFIDENCE_ASSESSMENT_SCHEMA_VERSION,
        point=point,
        min_value=min_value,
        max_value=max_value,
        coverage=coverage,
        contradiction_penalty=contradiction_penalty,
        explanation=explanation,
    )
    return assessment


def validate_confidence_bounds(assessment: ConfidenceAssessmentV1) -> None:
    if assessment.min_value > assessment.max_value:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Confidence min cannot exceed max",
            details={"min": assessment.min_value, "max": assessment.max_value},
        )
    if not (assessment.min_value <= assessment.point <= assessment.max_value):
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Confidence point must fall within min/max range",
            details={
                "point": assessment.point,
                "min": assessment.min_value,
                "max": assessment.max_value,
            },
        )


def _coverage(supporting_count: int, total_visible: int) -> float:
    if total_visible <= 0:
        return 0.0
    return min(1.0, supporting_count / total_visible)
