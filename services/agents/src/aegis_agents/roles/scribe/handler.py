"""SCRIBE role handler."""

from __future__ import annotations

from typing import Any

from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.scribe.schemas import SCRIBE_NARRATIVE_OUTPUT_SCHEMA
from aegis_contracts.entities import AgentRole
from aegis_reports.service import ReportService


class ScribeRoleHandler:
    role = AgentRole.SCRIBE
    prompt_version = "phase23-scribe-v1"

    def __init__(self, *, report_service: ReportService | None = None) -> None:
        self._reports = report_service or ReportService()

    def output_schema(self) -> dict[str, Any]:
        return SCRIBE_NARRATIVE_OUTPUT_SCHEMA

    def system_prompt(self) -> str:
        return (
            "You are AEGIS SCRIBE. Produce evidence-linked incident summary prose only. "
            "Distinguish observed facts, persisted events, model scores, graph risk, "
            "investigation evidence, ORACLE hypotheses, BASTION proposals, and WARDEN policy "
            "decisions. Mark unsupported or uncertain claims explicitly. Never approve actions "
            "or recommend containment execution."
        )

    async def post_process(
        self,
        *,
        ctx: PostProcessContext,
        structured: dict[str, Any],
    ) -> None:
        task = await ctx.uow.agent_tasks.get_by_id(ctx.task_id)
        provider_id = task.provider_id if task is not None else None
        regenerate = "regenerate" in ctx.idempotency_key
        if structured.get("executiveSummary"):
            structured_claims = structured.get("claims", [])
        else:
            structured_claims = None
        await self._reports.generate_report(
            ctx.uow,
            run_id=ctx.run_id,
            incident_id=ctx.incident_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            trace_id=ctx.trace_id,
            provider_id=provider_id,
            prompt_version=self.prompt_version,
            narrative_claims=structured_claims,
            regenerate=regenerate,
        )
