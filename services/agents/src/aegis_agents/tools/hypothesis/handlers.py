"""ORACLE hypothesis tool handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.roles.oracle.grounding import build_grounding_context, ground_hypothesis_claims
from aegis_agents.roles.oracle.revision import build_revision
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.tools.context import ToolExecutionContext
from aegis_contracts.hypothesis import HypothesisStatusV1, VerificationRequestV1
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.versioning import VERIFICATION_REQUEST_SCHEMA_VERSION

HYPOTHESIS_TOOL_HANDLERS: dict[str, Any] = {}


async def handle_list_hypotheses(
    ctx: ToolExecutionContext,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    hypotheses = await ctx.uow.oracle_hypotheses.list_hypotheses_for_incident(ctx.incident_id)
    revisions = await ctx.uow.oracle_hypotheses.list_revisions_for_incident(ctx.incident_id)
    return {
        "hypotheses": [item.model_dump(by_alias=True, mode="json") for item in hypotheses],
        "revisions": [item.model_dump(by_alias=True, mode="json") for item in revisions],
    }


async def handle_create_hypothesis_revision(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    incident = await ctx.uow.incidents.get_by_id(ctx.incident_id)
    if incident is None:
        msg = f"Incident not found: {ctx.incident_id}"
        raise KeyError(msg)
    investigation = InvestigationDetailV1.model_validate(
        (await ctx.uow.investigation.get_detail(ctx.incident_id, incident.run_id)).model_dump()
    )
    grounding_context = build_grounding_context(investigation, ctx.visible_evidence_ids)
    grounded = ground_hypothesis_claims(
        structured_claims=payload.get("claims", []),
        supporting_evidence_ids=payload.get("supportingEvidenceIds", []),
        contradicting_evidence_ids=payload.get("contradictingEvidenceIds", []),
        context=grounding_context,
    )
    hypothesis_id = payload.get("hypothesisId") or new_runtime_id("hyp")
    prior_revisions = await ctx.uow.oracle_hypotheses.list_revisions_for_hypothesis(hypothesis_id)
    revision = build_revision(
        hypothesis_id=hypothesis_id,
        incident_id=ctx.incident_id,
        session_id=ctx.session_id,
        task_id=ctx.task_id,
        revision_number=len(prior_revisions) + 1,
        structured=payload,
        grounded=grounded,
    )
    if not prior_revisions:
        from aegis_agents.roles.oracle.revision import build_initial_hypothesis

        hypothesis = build_initial_hypothesis(
            incident_id=ctx.incident_id,
            family=revision.family,
            revision_id=revision.id,
        )
        hypothesis = hypothesis.model_copy(update={"id": hypothesis_id})
        revision = revision.model_copy(update={"hypothesis_id": hypothesis_id})
        await ctx.uow.oracle_hypotheses.add_hypothesis(hypothesis)
    else:
        existing_hypothesis = await ctx.uow.oracle_hypotheses.get_hypothesis(hypothesis_id)
        if existing_hypothesis is None:
            msg = f"Hypothesis not found: {hypothesis_id}"
            raise KeyError(msg)
        hypothesis = existing_hypothesis.model_copy(
            update={
                "current_revision_id": revision.id,
                "family": revision.family.value,
                "status": HypothesisStatusV1.ACTIVE.value,
            }
        )
        await ctx.uow.oracle_hypotheses.update_hypothesis(hypothesis)
    await ctx.uow.oracle_hypotheses.add_revision(revision)
    return {
        "hypothesisId": hypothesis_id,
        "revisionId": revision.id,
        "rejectedClaims": grounded.rejected_claims,
        "downgradedClaims": grounded.downgraded_claims,
    }


async def handle_request_trace_verification(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    verification = VerificationRequestV1(
        schema_version=VERIFICATION_REQUEST_SCHEMA_VERSION,
        id=new_runtime_id("vreq"),
        incident_id=ctx.incident_id,
        hypothesis_id=payload["hypothesisId"],
        session_id=ctx.session_id,
        task_id=ctx.task_id,
        purpose=payload["purpose"],
        target_evidence_ids=payload.get("targetEvidenceIds", []),
        idempotency_key=payload["idempotencyKey"],
        created_at=datetime.now(UTC),
    )
    existing = await ctx.uow.oracle_hypotheses.get_verification_by_idempotency(
        ctx.incident_id,
        verification.idempotency_key,
    )
    if existing is not None:
        return {"verificationId": existing.id, "replayed": True}
    await ctx.uow.oracle_hypotheses.add_verification_request(verification)
    return {"verificationId": verification.id, "replayed": False}


async def handle_retire_hypothesis(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    hypothesis_id = payload["hypothesisId"]
    hypothesis = await ctx.uow.oracle_hypotheses.get_hypothesis(hypothesis_id)
    if hypothesis is None:
        msg = f"Hypothesis not found: {hypothesis_id}"
        raise KeyError(msg)
    prior_revisions = await ctx.uow.oracle_hypotheses.list_revisions_for_hypothesis(hypothesis_id)
    latest = prior_revisions[-1] if prior_revisions else None
    if latest is None:
        msg = f"No revisions for hypothesis: {hypothesis_id}"
        raise KeyError(msg)
    revision = latest.model_copy(
        update={
            "id": new_runtime_id("hrev"),
            "revision_number": len(prior_revisions) + 1,
            "status": HypothesisStatusV1.RETIRED,
            "rationale": payload["rationale"],
            "created_at": datetime.now(UTC),
        }
    )
    await ctx.uow.oracle_hypotheses.add_revision(revision)
    hypothesis = hypothesis.model_copy(
        update={
            "current_revision_id": revision.id,
            "status": HypothesisStatusV1.RETIRED.value,
        }
    )
    await ctx.uow.oracle_hypotheses.update_hypothesis(hypothesis)
    return {"hypothesisId": hypothesis_id, "revisionId": revision.id}


HYPOTHESIS_TOOL_HANDLERS.update(
    {
        "list_hypotheses": handle_list_hypotheses,
        "create_hypothesis_revision": handle_create_hypothesis_revision,
        "request_trace_verification": handle_request_trace_verification,
        "retire_hypothesis": handle_retire_hypothesis,
    }
)
