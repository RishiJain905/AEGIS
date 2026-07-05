"""ORACLE confidence tests."""

from __future__ import annotations

import pytest
from aegis_agents.roles.oracle.confidence import (
    build_confidence_assessment,
    validate_confidence_bounds,
)
from aegis_contracts.errors import ContractValidationError


def test_confidence_bounds_enforced() -> None:
    assessment = build_confidence_assessment(
        {
            "point": 0.7,
            "min": 0.6,
            "max": 0.8,
            "coverage": 0.5,
            "contradictionPenalty": 0.1,
            "explanation": "ok",
        },
        supporting_count=2,
        contradicting_count=1,
        total_visible=4,
    )
    validate_confidence_bounds(assessment)


def test_invalid_confidence_range_rejected() -> None:
    with pytest.raises(ContractValidationError):
        build_confidence_assessment(
            {
                "point": 0.9,
                "min": 0.8,
                "max": 0.7,
                "coverage": 0.5,
                "contradictionPenalty": 0.1,
                "explanation": "bad",
            },
            supporting_count=1,
            contradicting_count=0,
            total_visible=2,
        )
