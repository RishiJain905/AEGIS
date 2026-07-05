"""Deterministic TRACE investigation plan builder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.entities import AlertV1
from aegis_contracts.investigation import (
    TraceInvestigationPlanV1,
    TraceSearchStepV1,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION

from aegis_agents.runtime.ids import new_runtime_id

_DEFAULT_MAX_HOPS = 3
_DEFAULT_MAX_TOOL_CALLS = 12
_DEFAULT_MAX_TOKENS = 8_000


def _seed_assets_from_alerts(alerts: list[AlertV1]) -> list[str]:
    seen: set[str] = set()
    seeds: list[str] = []
    for alert in alerts:
        if alert.asset_id not in seen:
            seen.add(alert.asset_id)
            seeds.append(alert.asset_id)
    return seeds


def _default_search_steps(seed_asset_ids: list[str]) -> list[TraceSearchStepV1]:
    steps: list[TraceSearchStepV1] = [
        TraceSearchStepV1(
            tool_name="list_existing_evidence",
            arguments={},
            purpose="Review visible evidence before expanding the graph",
        ),
        TraceSearchStepV1(
            tool_name="get_risk_scores",
            arguments={},
            purpose="Prioritize high-risk assets for bounded graph expansion",
        ),
    ]
    if seed_asset_ids:
        steps.append(
            TraceSearchStepV1(
                tool_name="get_asset",
                arguments={"assetId": seed_asset_ids[0]},
                purpose="Inspect the primary seed asset context",
            )
        )
        steps.append(
            TraceSearchStepV1(
                tool_name="get_relationships",
                arguments={"assetId": seed_asset_ids[0]},
                purpose="Enumerate first-hop relationships from the seed asset",
            )
        )
    return steps


def build_trace_plan(
    *,
    structured: dict[str, Any],
    triage: WatchtowerTriageResultV1 | None,
    alerts: list[AlertV1],
    incident_id: str,
    run_id: str,
    session_id: str,
    task_id: str,
) -> TraceInvestigationPlanV1:
    seed_asset_ids = list(structured.get("seedAssetIds", []))
    if not seed_asset_ids:
        if triage is not None and triage.grouped_alert_ids:
            alert_by_id = {alert.id: alert for alert in alerts}
            for alert_id in triage.grouped_alert_ids:
                alert = alert_by_id.get(alert_id)
                if alert is not None and alert.asset_id not in seed_asset_ids:
                    seed_asset_ids.append(alert.asset_id)
        if not seed_asset_ids:
            seed_asset_ids = _seed_assets_from_alerts(alerts)

    search_steps = [
        TraceSearchStepV1(
            tool_name=item["toolName"],
            arguments=item.get("arguments", {}),
            purpose=item["purpose"],
        )
        for item in structured.get("searchSteps", [])
        if item.get("toolName") and item.get("purpose")
    ]
    if not search_steps:
        search_steps = _default_search_steps(seed_asset_ids)

    rationale = structured.get("rationale") or (
        triage.escalation_rationale
        if triage is not None
        else "Bounded TRACE plan derived from incident alerts and triage context."
    )

    return TraceInvestigationPlanV1(
        schema_version=TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION,
        id=new_runtime_id("tpln"),
        incident_id=incident_id,
        run_id=run_id,
        session_id=session_id,
        task_id=task_id,
        seed_asset_ids=seed_asset_ids,
        time_window_start_sequence=structured.get("timeWindowStartSequence"),
        time_window_end_sequence=structured.get("timeWindowEndSequence"),
        max_hops=int(structured.get("maxHops", _DEFAULT_MAX_HOPS)),
        max_tool_calls=int(structured.get("maxToolCalls", _DEFAULT_MAX_TOOL_CALLS)),
        max_tokens=int(structured.get("maxTokens", _DEFAULT_MAX_TOKENS)),
        search_steps=search_steps,
        rationale=rationale,
        created_at=datetime.now(UTC),
    )
