"""BASTION role handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.roles.bastion.build import build_proposal_bundle, build_response_option
from aegis_agents.roles.bastion.grounding import (
    build_grounding_context,
    validate_response_option_grounding,
)
from aegis_agents.roles.bastion.schemas import BASTION_PROPOSAL_OUTPUT_SCHEMA
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.proposal_events import (
    build_incident_state_changed_event,
    build_proposal_created_event,
)
from aegis_contracts.entities import AgentRole, IncidentState
from aegis_persistence.sim_clock import run_sim_time


class BastionRoleHandler:
    role = AgentRole.BASTION
    prompt_version = "phase22-bastion-v1"

    def output_schema(self) -> dict[str, Any]:
        return BASTION_PROPOSAL_OUTPUT_SCHEMA

    def system_prompt(self) -> str:
        return (
            "You are AEGIS BASTION. Propose proportionate evidence-grounded response options "
            "using only allowlisted scenario commands. Include expected benefit, operational cost, "
            "reversibility, affected assets, prerequisites, monitoring, and uncertainty. "
            "Never execute containment actions."
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

        response_options = []
        for item in structured.get("responseOptions", []):
            validate_response_option_grounding(
                evidence_ids=item.get("evidenceIds", []),
                hypothesis_ids=item.get("hypothesisIds", []),
                scenario_command=item["scenarioCommand"],
                context=grounding_context,
                trace_id=ctx.trace_id,
            )
            response_options.append(build_response_option(item))

        if not response_options:
            return

        proposal, revision = build_proposal_bundle(
            incident_id=ctx.incident_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            structured=structured,
            response_options=response_options,
        )
        await ctx.uow.proposals.add_proposal(proposal)
        await ctx.uow.proposals.add_revision(revision)

        # Resolved once per turn: every event this post-process emits belongs to the same
        # instant on the run's virtual clock, and the clock cannot advance mid-turn.
        sim_time = await run_sim_time(ctx.uow, ctx.run_id)

        next_sequence = await ctx.uow.events.next_sequence(ctx.run_id)
        await ctx.uow.append_event(
            build_proposal_created_event(
                event_id=new_runtime_id("evt"),
                run_id=ctx.run_id,
                sequence=next_sequence,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                trace_id=ctx.trace_id,
                proposal_id=proposal.id,
                revision_id=revision.id,
                incident_id=ctx.incident_id,
                action_class=proposal.action_class.value,
                sim_time=sim_time,
            )
        )

        if incident.state not in {
            IncidentState.CONTAINMENT_PROPOSED,
            IncidentState.APPROVAL_PENDING,
        }:
            updated = incident.model_copy(
                update={
                    "state": IncidentState.CONTAINMENT_PROPOSED,
                    "updated_at": datetime.now(UTC),
                    "revision": incident.revision + 1,
                }
            )
            await ctx.uow.incidents.update_with_revision(
                updated,
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
                    previous_state=incident.state.value,
                    new_state=IncidentState.CONTAINMENT_PROPOSED.value,
                    sim_time=sim_time,
                )
            )
