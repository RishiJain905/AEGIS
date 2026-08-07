"""ORACLE role handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.entities import AgentRole
from aegis_contracts.hypothesis import (
    HypothesisStatusV1,
    VerificationRequestV1,
)
from aegis_contracts.versioning import VERIFICATION_REQUEST_SCHEMA_VERSION
from aegis_persistence.sim_clock import run_sim_time

from aegis_agents.roles.chaining import InvestigationChain
from aegis_agents.roles.oracle.comparison import build_hypothesis_comparison
from aegis_agents.roles.oracle.grounding import build_grounding_context, ground_hypothesis_claims
from aegis_agents.roles.oracle.revision import build_initial_hypothesis, build_revision
from aegis_agents.roles.oracle.schemas import ORACLE_HYPOTHESIS_OUTPUT_SCHEMA
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.investigation_events import (
    build_hypothesis_comparison_event,
    build_hypothesis_created_event,
    build_hypothesis_revised_event,
    build_verification_requested_event,
)


class OracleRoleHandler:
    role = AgentRole.ORACLE
    prompt_version = "phase21-oracle-v1"

    def __init__(self, chain: InvestigationChain | None = None) -> None:
        self._chain = chain or InvestigationChain()

    def output_schema(self) -> dict[str, Any]:
        return ORACLE_HYPOTHESIS_OUTPUT_SCHEMA

    def system_prompt(self) -> str:
        return (
            "You are AEGIS ORACLE. Generate multiple competing evidence-grounded hypotheses "
            "for the active investigation. Distinguish observed facts from inference, preserve "
            "contradictions and unknowns, and return structured output without hidden reasoning."
        )

    async def post_process(
        self,
        *,
        ctx: PostProcessContext,
        structured: dict[str, Any],
    ) -> None:
        incident = await ctx.uow.incidents.get_by_id(ctx.incident_id)
        if incident is None:
            msg = f"Incident not found: {ctx.incident_id}"
            raise KeyError(msg)

        investigation = await ctx.uow.investigation.get_detail(ctx.incident_id, ctx.run_id)
        grounding_context = build_grounding_context(investigation, ctx.visible_evidence_ids)
        persisted_revisions = []

        # Resolved once per turn: every event this post-process emits belongs to the same
        # instant on the run's virtual clock, and the clock cannot advance mid-turn.
        sim_time = await run_sim_time(ctx.uow, ctx.run_id)

        for item in structured.get("hypotheses", []):
            grounded = ground_hypothesis_claims(
                structured_claims=item.get("claims", []),
                supporting_evidence_ids=item.get("supportingEvidenceIds", []),
                contradicting_evidence_ids=item.get("contradictingEvidenceIds", []),
                context=grounding_context,
            )
            existing_id = item.get("existingHypothesisId")
            if existing_id:
                hypothesis = await ctx.uow.oracle_hypotheses.get_hypothesis(existing_id)
                if hypothesis is None:
                    continue
                prior_revisions = await ctx.uow.oracle_hypotheses.list_revisions_for_hypothesis(
                    existing_id
                )
                for prior in prior_revisions:
                    if prior.status == HypothesisStatusV1.ACTIVE:
                        superseded = prior.model_copy(
                            update={"status": HypothesisStatusV1.SUPERSEDED}
                        )
                        await ctx.uow.oracle_hypotheses.add_revision(superseded)
                revision_number = len(prior_revisions) + 1
                revision = build_revision(
                    hypothesis_id=existing_id,
                    incident_id=ctx.incident_id,
                    session_id=ctx.session_id,
                    task_id=ctx.task_id,
                    revision_number=revision_number,
                    structured=item,
                    grounded=grounded,
                )
                hypothesis = hypothesis.model_copy(
                    update={
                        "current_revision_id": revision.id,
                        "family": revision.family.value,
                        "status": HypothesisStatusV1.ACTIVE.value,
                    }
                )
                await ctx.uow.oracle_hypotheses.update_hypothesis(hypothesis)
                await ctx.uow.oracle_hypotheses.add_revision(revision)
                persisted_revisions.append(revision)
                next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
                await ctx.uow.append_event(
                    build_hypothesis_revised_event(
                        event_id=new_runtime_id("evt"),
                        run_id=ctx.run_id,
                        sequence=next_sequence,
                        session_id=ctx.session_id,
                        task_id=ctx.task_id,
                        trace_id=ctx.trace_id,
                        hypothesis_id=hypothesis.id,
                        revision_id=revision.id,
                        incident_id=ctx.incident_id,
                        sim_time=sim_time,
                    )
                )
                continue

            revision = build_revision(
                hypothesis_id=new_runtime_id("hyp"),
                incident_id=ctx.incident_id,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                revision_number=1,
                structured=item,
                grounded=grounded,
            )
            hypothesis = build_initial_hypothesis(
                incident_id=ctx.incident_id,
                family=revision.family,
                revision_id=revision.id,
            )
            hypothesis = hypothesis.model_copy(update={"id": revision.hypothesis_id})
            revision = revision.model_copy(update={"hypothesis_id": hypothesis.id})
            await ctx.uow.oracle_hypotheses.add_hypothesis(hypothesis)
            await ctx.uow.oracle_hypotheses.add_revision(revision)
            persisted_revisions.append(revision)
            next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
            await ctx.uow.append_event(
                build_hypothesis_created_event(
                    event_id=new_runtime_id("evt"),
                    run_id=ctx.run_id,
                    sequence=next_sequence,
                    session_id=ctx.session_id,
                    task_id=ctx.task_id,
                    trace_id=ctx.trace_id,
                    hypothesis_id=hypothesis.id,
                    revision_id=revision.id,
                    incident_id=ctx.incident_id,
                    sim_time=sim_time,
                )
            )

        comparison = build_hypothesis_comparison(
            incident_id=ctx.incident_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            revisions=persisted_revisions,
            summary=structured.get("comparisonSummary", ""),
        )
        if comparison is not None:
            await ctx.uow.oracle_hypotheses.add_comparison(comparison)
            next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
            await ctx.uow.append_event(
                build_hypothesis_comparison_event(
                    event_id=new_runtime_id("evt"),
                    run_id=ctx.run_id,
                    sequence=next_sequence,
                    session_id=ctx.session_id,
                    task_id=ctx.task_id,
                    trace_id=ctx.trace_id,
                    comparison_id=comparison.id,
                    incident_id=ctx.incident_id,
                    sim_time=sim_time,
                )
            )

        for index, request in enumerate(structured.get("verificationRequests", [])):
            hypothesis_index = int(request.get("hypothesisIndex", index))
            if hypothesis_index >= len(persisted_revisions):
                continue
            revision = persisted_revisions[hypothesis_index]
            verification = VerificationRequestV1(
                schema_version=VERIFICATION_REQUEST_SCHEMA_VERSION,
                id=new_runtime_id("vreq"),
                incident_id=ctx.incident_id,
                hypothesis_id=revision.hypothesis_id,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                purpose=request["purpose"],
                target_evidence_ids=request.get("targetEvidenceIds", []),
                idempotency_key=f"{ctx.idempotency_key}:verify:{index}",
                created_at=datetime.now(UTC),
            )
            existing = await ctx.uow.oracle_hypotheses.get_verification_by_idempotency(
                ctx.incident_id,
                verification.idempotency_key,
            )
            if existing is not None:
                continue
            await ctx.uow.oracle_hypotheses.add_verification_request(verification)
            next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
            await ctx.uow.append_event(
                build_verification_requested_event(
                    event_id=new_runtime_id("evt"),
                    run_id=ctx.run_id,
                    sequence=next_sequence,
                    session_id=ctx.session_id,
                    task_id=ctx.task_id,
                    trace_id=ctx.trace_id,
                    verification_id=verification.id,
                    hypothesis_id=verification.hypothesis_id,
                    incident_id=ctx.incident_id,
                    sim_time=sim_time,
                )
            )

        await self._chain.advance(
            ctx.uow,
            from_role=AgentRole.ORACLE,
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            initiator=ctx.initiator,
        )
