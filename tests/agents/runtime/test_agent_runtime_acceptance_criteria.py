"""Acceptance criteria mapped tests for Phase 19."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.grounding import validate_citations
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import DEFAULT_TOOL_REGISTRY
from aegis_contracts.agent_runtime import EvidenceCitationV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import EVIDENCE_CITATION_SCHEMA_VERSION


def test_invalid_evidence_citations_rejected_by_grounding() -> None:
    with pytest.raises(AgentRuntimeError) as exc:
        validate_citations(
            [
                EvidenceCitationV1(
                    schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                    evidence_id="evidence:evd_hidden",
                )
            ],
            visible_evidence_ids={"evidence:evd_synthetic_001"},
        )
    assert exc.value.code == AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE


def test_execution_tool_not_model_visible() -> None:
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.TRACE)
    with pytest.raises(AgentRuntimeError) as exc:
        authorize_tool_call(
            registry=DEFAULT_TOOL_REGISTRY,
            definition=definition,
            tool_name="execute_simulation_command",
        )
    assert exc.value.code == AgentRuntimeErrorCode.TOOL_UNAUTHORIZED
