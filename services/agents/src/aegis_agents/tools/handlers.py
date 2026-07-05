"""Tool handler implementations — no direct simulator mutation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.runtime.grounding import validate_citations
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.tools.context import ToolExecutionContext
from aegis_agents.tools.hypothesis import HYPOTHESIS_TOOL_HANDLERS
from aegis_agents.tools.investigation import INVESTIGATION_TOOL_HANDLERS
from aegis_agents.tools.proposal import PROPOSAL_TOOL_HANDLERS
from aegis_contracts import ActionClass, ActionProposalV1, HypothesisV1, ProposalStatus
from aegis_contracts.agent_runtime import AgentArtifactType, AgentArtifactV1, EvidenceCitationV1
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    AGENT_ARTIFACT_SCHEMA_VERSION,
    EVIDENCE_CITATION_SCHEMA_VERSION,
)


async def handle_list_evidence(ctx: ToolExecutionContext, _input: dict[str, Any]) -> dict[str, Any]:
    evidence = await ctx.uow.evidence.list_for_run(ctx.run_id)
    visible = [item for item in evidence if item.id in ctx.visible_evidence_ids]
    return {
        "evidenceIds": [item.id for item in visible],
        "summaries": [{"id": item.id, "summary": item.summary} for item in visible],
    }


async def handle_get_incident(ctx: ToolExecutionContext, _input: dict[str, Any]) -> dict[str, Any]:
    incident = await ctx.uow.incidents.get_by_id(ctx.incident_id)
    if incident is None:
        msg = f"Incident not found: {ctx.incident_id}"
        raise KeyError(msg)
    return {
        "incidentId": incident.id,
        "runId": incident.run_id,
        "state": incident.state.value,
    }


async def handle_create_hypothesis(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_ids = payload["evidenceIds"]
    citations = [
        EvidenceCitationV1(
            schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
            evidence_id=evidence_id,
        )
        for evidence_id in evidence_ids
    ]
    validate_citations(
        citations,
        visible_evidence_ids=ctx.visible_evidence_ids,
        trace_id=ctx.trace_id,
    )
    now = datetime.now(UTC)
    hypothesis = HypothesisV1(
        schema_version=1,
        id=new_runtime_id("hyp"),
        incident_id=ctx.incident_id,
        statement=payload["statement"],
        confidence=payload["confidence"],
        evidence_ids=evidence_ids,
        created_at=now,
    )
    await ctx.uow.hypotheses.add(hypothesis)
    artifact = AgentArtifactV1(
        schema_version=AGENT_ARTIFACT_SCHEMA_VERSION,
        id=new_runtime_id("aaf"),
        task_id=ctx.task_id,
        session_id=ctx.session_id,
        artifact_type=AgentArtifactType.HYPOTHESIS,
        payload={
            "hypothesisId": hypothesis.id,
            "statement": hypothesis.statement,
            "confidence": hypothesis.confidence,
            "evidenceIds": evidence_ids,
        },
        created_at=now,
    )
    await ctx.uow.agent_artifacts.add(artifact)
    return {"hypothesisId": hypothesis.id, "artifactId": artifact.id}


async def handle_create_action_proposal(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_ids = payload["evidenceIds"]
    citations = [
        EvidenceCitationV1(
            schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
            evidence_id=evidence_id,
        )
        for evidence_id in evidence_ids
    ]
    validate_citations(
        citations,
        visible_evidence_ids=ctx.visible_evidence_ids,
        trace_id=ctx.trace_id,
    )
    now = datetime.now(UTC)
    proposal = ActionProposalV1(
        schema_version=ACTION_PROPOSAL_SCHEMA_VERSION,
        id=new_runtime_id("prp"),
        incident_id=ctx.incident_id,
        agent_session_id=ctx.session_id,
        action_class=ActionClass(payload["actionClass"]),
        target_asset_id=payload["targetAssetId"],
        command=payload["command"],
        status=ProposalStatus.PENDING,
        rationale=payload.get("rationale", ""),
        revision=0,
        created_at=now,
    )
    await ctx.uow.action_proposals.add(proposal)
    return {"proposalId": proposal.id, "status": proposal.status.value}


TOOL_HANDLERS = {
    "list_evidence": handle_list_evidence,
    "get_incident": handle_get_incident,
    "create_hypothesis": handle_create_hypothesis,
    "create_action_proposal": handle_create_action_proposal,
    **INVESTIGATION_TOOL_HANDLERS,
    **HYPOTHESIS_TOOL_HANDLERS,
    **PROPOSAL_TOOL_HANDLERS,
}

__all__ = ["ToolExecutionContext", "TOOL_HANDLERS"]
