"""TRACE role handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import (
    EvidenceAttachmentV1,
    EvidenceProvenanceV1,
    EvidenceSourceType,
)
from aegis_contracts.versioning import EVIDENCE_ATTACHMENT_SCHEMA_VERSION
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.sim_clock import run_sim_time

from aegis_agents.roles.chaining import InvestigationChain
from aegis_agents.roles.common.schemas import TRACE_STEP_OUTPUT_SCHEMA
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.trace.candidates import rank_affected_assets
from aegis_agents.roles.trace.graph_expansion import expand_graph
from aegis_agents.roles.trace.planner import build_trace_plan
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.investigation_events import (
    build_evidence_attached_event,
    build_graph_overlay_event,
    build_plan_created_event,
)


class TraceRoleHandler:
    role = AgentRole.TRACE
    prompt_version = "phase20-trace-v1"

    def __init__(self, chain: InvestigationChain | None = None) -> None:
        self._chain = chain or InvestigationChain()

    def output_schema(self) -> dict[str, Any]:
        return TRACE_STEP_OUTPUT_SCHEMA

    def system_prompt(self) -> str:
        return (
            "You are AEGIS TRACE. Build bounded investigation plans, collect grounded evidence, "
            "and highlight affected graph assets. Return structured output with evidence citations."
        )

    async def post_process(
        self,
        *,
        ctx: PostProcessContext,
        structured: dict[str, Any],
    ) -> None:
        # Resolved once per turn: every event this post-process emits belongs to the same
        # instant on the run's virtual clock, and the clock cannot advance mid-turn.
        sim_time = await run_sim_time(ctx.uow, ctx.run_id)

        alerts = await ctx.uow.alerts.list_by_run(ctx.run_id)
        triage_results = await ctx.uow.investigation.list_triage_for_incident(ctx.incident_id)
        triage = triage_results[-1] if triage_results else None

        plan = build_trace_plan(
            structured=structured,
            triage=triage,
            alerts=alerts,
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
        )
        await ctx.uow.investigation.add_plan(plan)
        next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
        await ctx.uow.append_event(
            build_plan_created_event(
                event_id=new_runtime_id("evt"),
                run_id=ctx.run_id,
                sequence=next_sequence,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                trace_id=ctx.trace_id,
                plan_id=plan.id,
                incident_id=ctx.incident_id,
                sim_time=sim_time,
            )
        )

        evidence_ids = [
            item["evidenceId"]
            for item in structured.get("evidenceCitations", [])
            if item.get("evidenceId")
        ]
        now = datetime.now(UTC)
        for item in structured.get("evidenceAttachments", []):
            attachment = EvidenceAttachmentV1(
                schema_version=EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
                id=new_runtime_id("eatt"),
                incident_id=ctx.incident_id,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                provenance=EvidenceProvenanceV1(
                    source_type=EvidenceSourceType(item["sourceType"]),
                    source_id=item["sourceId"],
                    summary=item["summary"],
                    collected_by_tool=item.get("collectedByTool"),
                    collected_at_sequence=item.get("collectedAtSequence"),
                ),
                evidence_id=item.get("evidenceId"),
                asset_id=item.get("assetId"),
                is_contradiction=bool(item.get("isContradiction", False)),
                confidence=item["confidence"],
                rationale=item["rationale"],
                created_at=now,
            )
            await ctx.uow.investigation.add_evidence_attachment(attachment)
            next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
            await ctx.uow.append_event(
                build_evidence_attached_event(
                    event_id=new_runtime_id("evt"),
                    run_id=ctx.run_id,
                    sequence=next_sequence,
                    session_id=ctx.session_id,
                    task_id=ctx.task_id,
                    trace_id=ctx.trace_id,
                    attachment_id=attachment.id,
                    incident_id=ctx.incident_id,
                    is_contradiction=attachment.is_contradiction,
                    sim_time=sim_time,
                )
            )

        snapshot = await PostgresGraphSnapshotRepository(ctx.uow.session).get_latest_for_run(
            ctx.run_id
        )
        overlay = expand_graph(
            snapshot=snapshot,
            seed_asset_ids=plan.seed_asset_ids,
            max_hops=plan.max_hops,
            graph_highlights=structured.get("graphHighlights", []),
            edge_highlights=structured.get("edgeHighlights", []),
            overlay_rationale=structured.get("overlayRationale")
            or structured.get("rationale", "Bounded TRACE graph overlay"),
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
        )
        await ctx.uow.investigation.add_graph_overlay(overlay)
        next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
        await ctx.uow.append_event(
            build_graph_overlay_event(
                event_id=new_runtime_id("evt"),
                run_id=ctx.run_id,
                sequence=next_sequence,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                trace_id=ctx.trace_id,
                overlay_id=overlay.id,
                incident_id=ctx.incident_id,
                highlight_count=len(overlay.highlights),
                edge_highlight_count=len(overlay.edge_highlights),
                sim_time=sim_time,
            )
        )

        risk_scores = await ctx.uow.risk_scores.list_latest_by_run(ctx.run_id)
        candidates = rank_affected_assets(
            alerts=alerts,
            risk_scores=risk_scores,
            evidence_ids=evidence_ids,
            candidates_from_model=structured.get("candidateAssets", []),
            incident_id=ctx.incident_id,
        )
        for candidate in candidates:
            await ctx.uow.investigation.add_candidate_asset(candidate)

        await self._chain.advance(
            ctx.uow,
            from_role=AgentRole.TRACE,
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            initiator=ctx.initiator,
        )
