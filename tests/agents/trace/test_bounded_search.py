"""Budget enforcement tests for bounded TRACE searches."""

from __future__ import annotations

import pytest
from aegis_agents.roles.common.budgets import InvestigationBudgetTracker
from aegis_agents.roles.trace.collector import TraceCollector
from aegis_agents.roles.trace.graph_expansion import expand_graph
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode

from tests.agents.trace.helpers import make_evidence_attachment, make_linear_graph_snapshot


def test_tool_call_budget_exceeded() -> None:
    budget = InvestigationBudgetTracker(max_tool_calls=2, max_hops=4)
    budget.record_tool_call()
    budget.record_tool_call()
    with pytest.raises(AgentRuntimeError) as exc:
        budget.record_tool_call()
    assert exc.value.code == AgentRuntimeErrorCode.BUDGET_EXCEEDED
    assert exc.value.details["maxToolCalls"] == 2


def test_hop_budget_exceeded() -> None:
    budget = InvestigationBudgetTracker(max_tool_calls=10, max_hops=2)
    with pytest.raises(AgentRuntimeError) as exc:
        budget.record_tool_call(hops=3)
    assert exc.value.code == AgentRuntimeErrorCode.BUDGET_EXCEEDED
    assert exc.value.details["maxHops"] == 2


def test_graph_expansion_respects_max_hops() -> None:
    snapshot = make_linear_graph_snapshot()
    overlay = expand_graph(
        snapshot=snapshot,
        seed_asset_ids=["asset:seed-01"],
        max_hops=1,
        graph_highlights=[],
        edge_highlights=[],
        overlay_rationale="Bounded expansion",
        incident_id="incident:inc_synthetic_001",
        run_id=snapshot.run_id,
        session_id="agent-session:ags_synthetic_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )
    node_ids = {item.entity_id for item in overlay.highlights}
    assert "asset:seed-01" in node_ids
    assert "asset:hop-01" in node_ids
    assert "asset:hop-02" not in node_ids


@pytest.mark.asyncio
async def test_dedupe_attachments_preserves_unique_provenance() -> None:
    collector = TraceCollector()
    attachments = [
        make_evidence_attachment(attachment_id="eatt_001", source_id="evidence:evd_a"),
        make_evidence_attachment(attachment_id="eatt_002", source_id="evidence:evd_b"),
        make_evidence_attachment(attachment_id="eatt_003", source_id="evidence:evd_a"),
    ]
    unique = await collector.dedupe_attachments(attachments)
    assert len(unique) == 2
    assert {item.id for item in unique} == {"eatt_001", "eatt_002"}
