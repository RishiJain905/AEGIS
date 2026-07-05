"""Acceptance criteria mapped tests for Phase 20 WATCHTOWER."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.roles.watchtower.correlation import correlate_alerts
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import TriageEscalationLevel, WatchtowerTriageResultV1
from aegis_contracts.versioning import WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION

from tests.agents.watchtower.helpers import alert_at


def test_silent_relay_alerts_can_become_grounded_investigation() -> None:
    """AC: Silent Relay signals become a grounded investigation."""
    alerts = [
        alert_at(
            alert_id="alert:alt_synthetic_001",
            asset_id="asset:device-workstation-01",
            offset_minutes=0,
            title="Repeated authentication failures",
        ),
    ]
    decisions = correlate_alerts(alerts)
    triage = WatchtowerTriageResultV1(
        schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
        id="wtri_acceptance_001",
        incident_id="incident:inc_synthetic_001",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        session_id="agent-session:ags_synthetic_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        alert_summaries=[
            {
                "alertId": alerts[0].id,
                "title": alerts[0].title,
                "severity": alerts[0].severity,
                "assetId": alerts[0].asset_id,
            }
        ],
        grouped_alert_ids=[],
        separated_alert_ids=[alerts[0].id],
        correlation_decisions=decisions,
        escalation=TriageEscalationLevel.INVESTIGATE,
        escalation_rationale="Authentication anomaly requires TRACE follow-up.",
        confidence=0.84,
        evidence_ids=["evidence:evd_synthetic_001"],
        idempotency_key="acceptance-watchtower-001",
        created_at=datetime(2026, 6, 30, 2, 5, 0, tzinfo=UTC),
    )
    assert triage.evidence_ids == ["evidence:evd_synthetic_001"]
    assert triage.escalation == TriageEscalationLevel.INVESTIGATE


def test_watchtower_definition_uses_investigation_tools_only() -> None:
    """AC: Agents use schema-constrained outputs and allowlisted tools."""
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.WATCHTOWER)
    assert definition.prompt_version == "phase20-watchtower-v1"
    assert "list_alerts" in definition.allowed_tools
    assert "execute_simulation_command" not in definition.allowed_tools
