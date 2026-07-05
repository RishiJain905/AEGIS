"""Phase 22 proposal tool handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.roles.bastion.build import build_proposal_bundle, build_response_option
from aegis_agents.roles.bastion.grounding import (
    build_grounding_context,
    validate_response_option_grounding,
)
from aegis_agents.tools.context import ToolExecutionContext

PROPOSAL_TOOL_HANDLERS: dict[str, Any] = {}


async def handle_list_proposals(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    del payload
    proposals = await ctx.uow.proposals.list_proposals_for_incident(ctx.incident_id)
    revisions = await ctx.uow.proposals.list_revisions_for_incident(ctx.incident_id)
    decisions = await ctx.uow.proposals.list_policy_decisions_for_incident(ctx.incident_id)
    return {
        "proposals": [item.model_dump(by_alias=True, mode="json") for item in proposals],
        "revisions": [item.model_dump(by_alias=True, mode="json") for item in revisions],
        "policyDecisions": [item.model_dump(by_alias=True, mode="json") for item in decisions],
    }


async def handle_create_response_proposal(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    investigation = await ctx.uow.investigation.get_detail(ctx.incident_id, ctx.run_id)
    grounding_context = build_grounding_context(investigation, ctx.visible_evidence_ids)
    response_options = []
    for item in payload.get("responseOptions", []):
        validate_response_option_grounding(
            evidence_ids=item.get("evidenceIds", []),
            hypothesis_ids=item.get("hypothesisIds", []),
            scenario_command=item["scenarioCommand"],
            context=grounding_context,
            trace_id=ctx.trace_id,
        )
        response_options.append(build_response_option(item))

    proposal, revision = build_proposal_bundle(
        incident_id=ctx.incident_id,
        session_id=ctx.session_id,
        task_id=ctx.task_id,
        structured=payload,
        response_options=response_options,
    )
    await ctx.uow.proposals.add_proposal(proposal)
    await ctx.uow.proposals.add_revision(revision)
    return {
        "proposalId": proposal.id,
        "revisionId": revision.id,
        "status": proposal.status.value,
        "createdAt": datetime.now(UTC).isoformat(),
    }


PROPOSAL_TOOL_HANDLERS.update(
    {
        "list_proposals": handle_list_proposals,
        "create_response_proposal": handle_create_response_proposal,
    }
)
