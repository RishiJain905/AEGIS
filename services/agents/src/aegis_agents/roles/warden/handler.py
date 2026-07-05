"""WARDEN role handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.roles.bastion.schemas import WARDEN_POLICY_OUTPUT_SCHEMA
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.warden.evaluation import build_policy_input
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.proposal_events import (
    build_incident_state_changed_event,
    build_policy_evaluated_event,
)
from aegis_contracts.entities import AgentRole, IncidentState, ProposalStatus
from aegis_contracts.proposals import PolicyOutcomeV1
from aegis_policy import PolicyEngine


class WardenRoleHandler:
    role = AgentRole.WARDEN
    prompt_version = "phase22-warden-v1"

    def __init__(self, *, policy_engine: PolicyEngine | None = None) -> None:
        self._policy = policy_engine or PolicyEngine()

    def output_schema(self) -> dict[str, Any]:
        return WARDEN_POLICY_OUTPUT_SCHEMA

    def system_prompt(self) -> str:
        return (
            "You are AEGIS WARDEN. Provide concise non-authoritative prose explaining policy "
            "evaluation context. Policy allow/block/approval decisions are computed "
            "deterministically by the platform and cannot be overridden by model output."
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

        explanation_prose = structured.get("explanationProse", "")
        target_ids = set(structured.get("proposalIds", []))
        proposals = await ctx.uow.proposals.list_proposals_for_incident(ctx.incident_id)
        if target_ids:
            proposals = [proposal for proposal in proposals if proposal.id in target_ids]

        approval_required = False
        for proposal in proposals:
            if proposal.status not in {ProposalStatus.PENDING}:
                continue
            if not proposal.current_revision_id:
                continue
            revision = await ctx.uow.proposals.get_revision(proposal.current_revision_id)
            if revision is None:
                continue

            asset_criticality = await self._asset_criticality(
                ctx,
                revision.response_options[0].target_asset_id
                if revision.response_options
                else proposal.target_asset_id,
            )
            policy_input = build_policy_input(
                proposal=proposal,
                revision=revision,
                incident_state=incident.state,
                asset_criticality=asset_criticality,
                scenario_restricted=True,
            )
            decision = self._policy.evaluate(
                policy_input,
                decision_id=new_runtime_id("pdc"),
                incident_id=ctx.incident_id,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                explanation_prose=explanation_prose,
            )
            await ctx.uow.proposals.add_policy_decision(decision)

            if decision.outcome == PolicyOutcomeV1.BLOCK:
                updated = proposal.model_copy(update={"status": ProposalStatus.REJECTED})
            elif decision.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED:
                updated = proposal.model_copy(update={"status": ProposalStatus.PENDING})
                approval_required = True
            else:
                updated = proposal.model_copy(update={"status": ProposalStatus.APPROVED})
            await ctx.uow.proposals.update_proposal(updated)

            next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
            await ctx.uow.append_event(
                build_policy_evaluated_event(
                    event_id=new_runtime_id("evt"),
                    run_id=ctx.run_id,
                    sequence=next_sequence,
                    session_id=ctx.session_id,
                    task_id=ctx.task_id,
                    trace_id=ctx.trace_id,
                    proposal_id=proposal.id,
                    revision_id=revision.id,
                    incident_id=ctx.incident_id,
                    outcome=decision.outcome.value,
                )
            )

        if approval_required and incident.state != IncidentState.APPROVAL_PENDING:
            previous = incident.state
            updated_incident = incident.model_copy(
                update={
                    "state": IncidentState.APPROVAL_PENDING,
                    "updated_at": datetime.now(UTC),
                    "revision": incident.revision + 1,
                }
            )
            await ctx.uow.incidents.update_with_revision(
                updated_incident,
                expected_revision=incident.revision,
            )
            next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
            await ctx.uow.append_event(
                build_incident_state_changed_event(
                    event_id=new_runtime_id("evt"),
                    run_id=ctx.run_id,
                    sequence=next_sequence,
                    session_id=ctx.session_id,
                    trace_id=ctx.trace_id,
                    incident_id=ctx.incident_id,
                    previous_state=previous.value,
                    new_state=IncidentState.APPROVAL_PENDING.value,
                )
            )

    async def _asset_criticality(self, ctx: PostProcessContext, asset_id: str) -> float:
        from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository

        graph_repo = PostgresGraphSnapshotRepository(ctx.uow.session)
        snapshot = await graph_repo.get_latest_for_run(ctx.run_id)
        if snapshot is not None:
            for node in snapshot.nodes:
                if node.id == asset_id:
                    return node.criticality
        scores = await ctx.uow.risk_scores.list_by_run(ctx.run_id)
        for score in scores:
            if score.asset_id == asset_id:
                return min(1.0, score.total)
        return 0.5
