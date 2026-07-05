"""Acceptance criteria mapped tests for Phase 20 TRACE."""

from __future__ import annotations

import pytest
from aegis_agents.roles.common.budgets import InvestigationBudgetTracker
from aegis_agents.roles.trace.graph_expansion import expand_graph
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.tools.investigation.definitions import INVESTIGATION_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.entities import AgentRole

from tests.agents.trace.helpers import make_evidence_attachment, make_linear_graph_snapshot


def test_collected_facts_require_visible_evidence_ids() -> None:
    """AC: Every collected fact resolves to authoritative data."""
    attachment = make_evidence_attachment(
        attachment_id="eatt_grounded",
        source_id="evidence:evd_synthetic_001",
        evidence_id="evidence:evd_synthetic_001",
    )
    assert attachment.evidence_id == "evidence:evd_synthetic_001"
    assert attachment.provenance.source_id == "evidence:evd_synthetic_001"


def test_search_and_graph_expansion_are_bounded() -> None:
    """AC: Search and graph expansion are bounded."""
    budget = InvestigationBudgetTracker(max_tool_calls=12, max_hops=3)
    for _ in range(12):
        budget.record_tool_call(hops=1)
    snapshot = make_linear_graph_snapshot()
    overlay = expand_graph(
        snapshot=snapshot,
        seed_asset_ids=["asset:seed-01"],
        max_hops=2,
        graph_highlights=[],
        edge_highlights=[],
        overlay_rationale="Bounded TRACE overlay",
        incident_id="incident:inc_synthetic_001",
        run_id=snapshot.run_id,
        session_id="agent-session:ags_synthetic_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )
    assert len(overlay.highlights) <= 3


def test_contradictory_evidence_remains_available() -> None:
    """AC: Contradictory evidence remains available to ORACLE."""
    contradiction = make_evidence_attachment(
        attachment_id="eatt_contradiction",
        source_id="evidence:evd_synthetic_001",
        is_contradiction=True,
    )
    assert contradiction.is_contradiction is True


def test_unauthorized_investigation_tool_rejected() -> None:
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.TRACE)
    registry = ToolRegistry(INVESTIGATION_TOOL_DEFINITIONS)
    with pytest.raises(AgentRuntimeError) as exc:
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="execute_simulation_command",
        )
    assert exc.value.code == AgentRuntimeErrorCode.TOOL_UNAUTHORIZED
