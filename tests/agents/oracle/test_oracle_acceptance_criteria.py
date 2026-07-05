"""ORACLE acceptance criteria tests."""

from __future__ import annotations

from aegis_agents.roles.oracle.comparison import build_hypothesis_comparison
from aegis_agents.roles.oracle.schemas import ORACLE_HYPOTHESIS_OUTPUT_SCHEMA
from aegis_agents.roles.registry import get_role_handler
from aegis_contracts.entities import AgentRole


def test_oracle_handler_registered_with_phase21_prompt() -> None:
    handler = get_role_handler(AgentRole.ORACLE)
    assert handler is not None
    assert handler.prompt_version == "phase21-oracle-v1"


def test_oracle_output_schema_requires_multiple_hypotheses() -> None:
    assert ORACLE_HYPOTHESIS_OUTPUT_SCHEMA["properties"]["hypotheses"]["minItems"] >= 2


def test_comparison_artifact_requires_two_entries() -> None:
    comparison = build_hypothesis_comparison(
        incident_id="incident:inc_001",
        session_id="agent-session:ags_001",
        task_id="atk_001",
        revisions=[],
        summary="not enough",
    )
    assert comparison is None
