"""WATCHTOWER role handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import (
    AlertCorrelationDecisionV1,
    EvidenceAttachmentV1,
    EvidenceProvenanceV1,
    EvidenceSourceType,
    TriageEscalationLevel,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import (
    EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
    WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
)
from aegis_persistence.sim_clock import run_sim_time

from aegis_agents.roles.chaining import InvestigationChain
from aegis_agents.roles.common.schemas import WATCHTOWER_TRIAGE_OUTPUT_SCHEMA
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.watchtower.incident_state import apply_triage_to_incident
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.investigation_events import (
    build_evidence_attached_event,
    build_triage_completed_event,
)

_DEFAULT_RATIONALE = "Deterministic correlation completed; investigation recommended."
_DEFAULT_CONFIDENCE = 0.7


def _escalation(raw: Any) -> TriageEscalationLevel:
    try:
        return TriageEscalationLevel(raw)
    except ValueError:
        return TriageEscalationLevel.INVESTIGATE


def _source_type(evidence_id: str) -> EvidenceSourceType:
    """A citation names a run event or an agent-authored evidence record (see
    ``CitableEvidenceId``); the provenance has a distinct source type for each."""
    if evidence_id.startswith("evt_"):
        return EvidenceSourceType.EVENT
    return EvidenceSourceType.EXISTING_EVIDENCE


class WatchtowerRoleHandler:
    role = AgentRole.WATCHTOWER
    prompt_version = "phase20-watchtower-v1"

    def __init__(self, chain: InvestigationChain | None = None) -> None:
        self._chain = chain or InvestigationChain()

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

        citations = [
            item
            for item in structured.get("evidenceCitations", [])
            if item.get("evidenceId")
        ]
        evidence_ids = [item["evidenceId"] for item in citations]
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
            # Defaulted rather than indexed: WATCHTOWER now also runs on autonomy lane
            # turns against a case the detection engine opened, and a local model that
            # drops a field there would otherwise lose the whole triage to a KeyError.
            # The defaults match the deterministic coordinator's, so a partial answer
            # still enriches the case instead of failing it.
            escalation=_escalation(structured.get("escalation")),
            escalation_rationale=str(
                structured.get("escalationRationale") or _DEFAULT_RATIONALE
            ),
            confidence=float(structured.get("confidence") or _DEFAULT_CONFIDENCE),
            evidence_ids=evidence_ids,
            idempotency_key=ctx.idempotency_key,
            created_at=now,
        )
        await ctx.uow.investigation.add_triage(triage)
        # Resolved once per turn: every event this post-process emits belongs to the same
        # instant on the run's virtual clock, and the clock cannot advance mid-turn.
        sim_time = await run_sim_time(ctx.uow, ctx.run_id)
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
                # The run's virtual clock, not ``now``: ``created_at`` on the triage row
                # above is wall-clock, but the chronicle sorts on the event's sim_time.
                sim_time=sim_time,
            )
        )

        await self._attach_cited_evidence(
            ctx, triage=triage, citations=citations, sim_time=sim_time, now=now
        )

        incident = await ctx.uow.incidents.get_by_id(ctx.incident_id)
        if incident is not None:
            await apply_triage_to_incident(
                ctx.uow,
                incident=incident,
                triage=triage,
                session_id=ctx.session_id,
                trace_id=ctx.trace_id,
                sim_time=sim_time,
            )

        await self._chain.advance(
            ctx.uow,
            from_role=AgentRole.WATCHTOWER,
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            initiator=ctx.initiator,
            escalation=triage.escalation,
        )

    async def _attach_cited_evidence(
        self,
        ctx: PostProcessContext,
        *,
        triage: WatchtowerTriageResultV1,
        citations: list[dict[str, Any]],
        sim_time: datetime,
        now: datetime,
    ) -> None:
        """Project the triage's own citations into the case's evidence.

        The citations are the grounding the escalation rests on, and until now they lived
        only inside the triage row: the operator's EVIDENCE panel reads evidence
        attachments, whose sole producer was TRACE. A triage that concluded MONITOR — the
        false-positive verdict, which by design never chains an investigation — therefore
        left a case whose every panel was empty even though the platform had looked at it
        and had grounds for the answer.
        """
        attached = await ctx.uow.investigation.list_evidence_attachments(ctx.incident_id)
        seen = {item.evidence_id for item in attached if item.evidence_id is not None}
        for item in citations:
            evidence_id = item["evidenceId"]
            # Grounding already rejected citations outside the catalogue before
            # post-processing; this is the belt to that brace, and it also skips a
            # citation the same case already carries rather than stacking duplicates.
            if evidence_id in seen:
                continue
            if ctx.visible_evidence_ids and evidence_id not in ctx.visible_evidence_ids:
                continue
            seen.add(evidence_id)
            rationale = str(item.get("rationale") or triage.escalation_rationale)
            attachment = EvidenceAttachmentV1(
                schema_version=EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
                id=new_runtime_id("eatt"),
                incident_id=ctx.incident_id,
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                provenance=EvidenceProvenanceV1(
                    source_type=_source_type(evidence_id),
                    source_id=evidence_id,
                    summary=rationale[:2048],
                ),
                evidence_id=evidence_id,
                confidence=triage.confidence,
                rationale=rationale[:2048],
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
