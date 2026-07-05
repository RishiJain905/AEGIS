"""WATCHTOWER role handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import (
    AlertCorrelationDecisionV1,
    TriageEscalationLevel,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION

from aegis_agents.roles.common.schemas import WATCHTOWER_TRIAGE_OUTPUT_SCHEMA
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.investigation_events import build_triage_completed_event


class WatchtowerRoleHandler:
    role = AgentRole.WATCHTOWER
    prompt_version = "phase20-watchtower-v1"

    def output_schema(self) -> dict[str, Any]:
        return WATCHTOWER_TRIAGE_OUTPUT_SCHEMA

    def system_prompt(self) -> str:
        return (
            "You are AEGIS WATCHTOWER. Triage and correlate alerts for the incident. "
            "Return grounded structured output with escalation rationale and evidence citations."
        )

    async def post_process(
        self,
        *,
        ctx: PostProcessContext,
        structured: dict[str, Any],
    ) -> None:
        existing = await ctx.uow.investigation.get_triage_by_idempotency(
            ctx.incident_id,
            ctx.idempotency_key,
        )
        if existing is not None:
            return

        evidence_ids = [
            item["evidenceId"]
            for item in structured.get("evidenceCitations", [])
            if item.get("evidenceId")
        ]
        correlation_decisions = [
            AlertCorrelationDecisionV1(
                alert_ids=item["alertIds"],
                decision=item["decision"],
                rationale=item["rationale"],
                factors=item.get("factors", []),
            )
            for item in structured.get("correlationDecisions", [])
        ]
        now = datetime.now(UTC)
        triage = WatchtowerTriageResultV1(
            schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
            id=new_runtime_id("wtri"),
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            alert_summaries=structured.get("alertSummaries", []),
            grouped_alert_ids=structured.get("groupedAlertIds", []),
            separated_alert_ids=structured.get("separatedAlertIds", []),
            correlation_decisions=correlation_decisions,
            escalation=TriageEscalationLevel(structured["escalation"]),
            escalation_rationale=structured["escalationRationale"],
            confidence=structured["confidence"],
            evidence_ids=evidence_ids,
            idempotency_key=ctx.idempotency_key,
            created_at=now,
        )
        await ctx.uow.investigation.add_triage(triage)
        next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
        await ctx.uow.append_event(
            build_triage_completed_event(
                event_id=new_runtime_id("evt"),
                run_id=ctx.run_id,
                sequence=next_sequence,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                trace_id=ctx.trace_id,
                triage_id=triage.id,
                incident_id=ctx.incident_id,
                escalation=triage.escalation.value,
            )
        )
