"""Deterministic template-only report generation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.reports import (
    AfterActionReportSourceV1,
    AfterActionReportV1,
    ReportCitationKindV1,
    ReportCitationV1,
    ReportClaimCategoryV1,
    ReportClaimV1,
    ReportGenerationModeV1,
)
from aegis_contracts.versioning import (
    AFTER_ACTION_REPORT_SCHEMA_VERSION,
    REPORT_CITATION_SCHEMA_VERSION,
    REPORT_CLAIM_SCHEMA_VERSION,
)

#: Terminal statuses whose task is a real AI-teammate interaction worth recording.
_TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True)
class AgentTaskFact:
    """A terminal run-scoped agent task, distilled for the deterministic template.

    Run-scoped (copilot/lane) tasks leave no incident-keyed artifacts, so the report
    records the interaction itself: which role, what outcome, and the failure reason
    when there was one. Pure data — the assembler builds these from persisted rows.
    """

    task_id: str
    session_id: str
    role: str | None
    status: str
    error_message: str | None = None


def _checksum(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _citation(
    *,
    kind: ReportCitationKindV1,
    reference_id: str,
    label: str,
    sequence: int | None = None,
) -> ReportCitationV1:
    return ReportCitationV1(
        schema_version=REPORT_CITATION_SCHEMA_VERSION,
        kind=kind,
        reference_id=reference_id,
        label=label,
        sequence=sequence,
    )


def build_template_report(
    *,
    report_id: str,
    version_number: int,
    source: AfterActionReportSourceV1,
    investigation: InvestigationDetailV1,
    session_id: str | None = None,
    task_id: str | None = None,
    provider_id: str | None = None,
    prompt_version: str | None = None,
    grounding_fallback: bool = False,
    generation_mode: ReportGenerationModeV1 = ReportGenerationModeV1.DETERMINISTIC,
    narrative_claims: Sequence[ReportClaimV1] | None = None,
    agent_tasks: Sequence[AgentTaskFact] | None = None,
) -> AfterActionReportV1:
    claims: list[ReportClaimV1] = []
    claim_index = 0

    summary = source.investigation_summary
    title = str(summary.get("incidentTitle", "Incident after-action report"))
    incident_state = str(summary.get("incidentState", "open"))

    claim_index += 1
    claims.append(
        ReportClaimV1(
            schema_version=REPORT_CLAIM_SCHEMA_VERSION,
            claim_id=f"claim_{claim_index:03d}",
            category=ReportClaimCategoryV1.OBSERVED_FACT,
            text=f"Incident '{title}' concluded investigation phase in state '{incident_state}'.",
            citations=[
                _citation(
                    kind=ReportCitationKindV1.EVENT,
                    reference_id=source.event_ids[0] if source.event_ids else "evt_unknown",
                    label="Earliest persisted event",
                    sequence=source.source_sequence_from,
                )
            ],
        )
    )

    for attachment in investigation.evidence_attachments[:12]:
        claim_index += 1
        evidence_id = attachment.evidence_id or attachment.id
        claims.append(
            ReportClaimV1(
                schema_version=REPORT_CLAIM_SCHEMA_VERSION,
                claim_id=f"claim_{claim_index:03d}",
                category=ReportClaimCategoryV1.INVESTIGATION_EVIDENCE,
                text=attachment.rationale,
                citations=[
                    _citation(
                        kind=ReportCitationKindV1.EVIDENCE,
                        reference_id=evidence_id,
                        label=attachment.id,
                    )
                ],
            )
        )

    for hypothesis in investigation.hypotheses[:6]:
        revision = next(
            (
                item
                for item in investigation.hypothesis_revisions
                if item.hypothesis_id == hypothesis.id and item.id == hypothesis.current_revision_id
            ),
            None,
        )
        if revision is None:
            continue
        claim_index += 1
        claims.append(
            ReportClaimV1(
                schema_version=REPORT_CLAIM_SCHEMA_VERSION,
                claim_id=f"claim_{claim_index:03d}",
                category=ReportClaimCategoryV1.ORACLE_HYPOTHESIS,
                text=revision.claim,
                confidence=revision.confidence.point,
                uncertainty=revision.confidence.explanation,
                citations=[
                    _citation(
                        kind=ReportCitationKindV1.HYPOTHESIS,
                        reference_id=hypothesis.id,
                        label=revision.family.value,
                    )
                ],
            )
        )

    for proposal in investigation.proposals[:6]:
        proposal_revision = next(
            (
                item
                for item in investigation.proposal_revisions
                if item.proposal_id == proposal.id and item.id == proposal.current_revision_id
            ),
            None,
        )
        claim_index += 1
        claims.append(
            ReportClaimV1(
                schema_version=REPORT_CLAIM_SCHEMA_VERSION,
                claim_id=f"claim_{claim_index:03d}",
                category=ReportClaimCategoryV1.BASTION_PROPOSAL,
                text=proposal.rationale,
                citations=[
                    _citation(
                        kind=ReportCitationKindV1.PROPOSAL,
                        reference_id=proposal.id,
                        label=proposal.scenario_command or proposal.action_class.value,
                    ),
                    *(
                        [
                            _citation(
                                kind=ReportCitationKindV1.PROPOSAL,
                                reference_id=proposal_revision.id,
                                label=f"Revision {proposal_revision.revision_number}",
                            )
                        ]
                        if proposal_revision
                        else []
                    ),
                ],
            )
        )

    for decision in investigation.policy_decisions[:6]:
        claim_index += 1
        claims.append(
            ReportClaimV1(
                schema_version=REPORT_CLAIM_SCHEMA_VERSION,
                claim_id=f"claim_{claim_index:03d}",
                category=ReportClaimCategoryV1.WARDEN_POLICY_DECISION,
                text=decision.explanation_prose or f"Policy outcome: {decision.outcome.value}",
                citations=[
                    _citation(
                        kind=ReportCitationKindV1.POLICY_DECISION,
                        reference_id=decision.id,
                        label=decision.outcome.value,
                    ),
                    _citation(
                        kind=ReportCitationKindV1.PROPOSAL,
                        reference_id=decision.proposal_id,
                        label="Evaluated proposal",
                    ),
                ],
            )
        )

    # Run-scoped (copilot/lane) tasks leave no incident-keyed artifacts, so their
    # terminal outcomes are recorded as claims here — the report must not read as if
    # the AI teammate never ran when it demonstrably did.
    for task in agent_tasks or []:
        if task.status not in _TERMINAL_TASK_STATUSES:
            continue
        claim_index += 1
        role = task.role or "agent"
        if task.status == "completed":
            text = f"{role} completed task {task.task_id} in session {task.session_id}."
        elif task.status == "cancelled":
            text = (
                f"{role} task {task.task_id} was cancelled: "
                f"{task.error_message or 'the run ended before it finished'}."
            )
        else:
            text = (
                f"{role} task {task.task_id} failed: "
                f"{task.error_message or 'no failure reason was recorded'}."
            )
        claims.append(
            ReportClaimV1(
                schema_version=REPORT_CLAIM_SCHEMA_VERSION,
                claim_id=f"claim_{claim_index:03d}",
                category=ReportClaimCategoryV1.AGENT_INFERENCE,
                text=text,
                citations=[
                    _citation(
                        kind=ReportCitationKindV1.AGENT_TASK,
                        reference_id=task.task_id,
                        label=task.task_id,
                    ),
                    _citation(
                        kind=ReportCitationKindV1.AGENT_SESSION,
                        reference_id=task.session_id,
                        label=task.session_id,
                    ),
                ],
            )
        )

    # Grounded model claims are appended here rather than merged by the caller so the
    # checksum below covers the full claim set actually persisted.
    if narrative_claims:
        claims.extend(narrative_claims)

    contradictions = [item.summary for item in investigation.hypothesis_comparisons if item.summary]
    uncertainties = [
        item
        for revision in investigation.hypothesis_revisions
        for item in revision.unknowns
    ][:8]

    terminal_tasks = [task for task in agent_tasks or [] if task.status in _TERMINAL_TASK_STATUSES]
    has_agent_artifacts = bool(
        investigation.triage_results
        or investigation.hypotheses
        or investigation.proposals
        or investigation.policy_decisions
        or terminal_tasks
    )
    summary_parts = [
        f"Deterministic after-action report for incident '{title}'.",
        f"Evidence attachments: {len(investigation.evidence_attachments)}.",
        f"Hypotheses: {len(investigation.hypotheses)}.",
        f"Proposals: {len(investigation.proposals)}.",
        f"Policy decisions: {len(investigation.policy_decisions)}.",
    ]
    if terminal_tasks:
        completed = sum(1 for task in terminal_tasks if task.status == "completed")
        failed = sum(1 for task in terminal_tasks if task.status == "failed")
        summary_parts.append(
            f"Agent tasks: {len(terminal_tasks)} ({completed} completed, {failed} failed)."
        )
    if generation_mode is ReportGenerationModeV1.DETERMINISTIC and not has_agent_artifacts:
        # The degraded case the operator most needs flagged: the run stopped without any
        # agent investigation, so everything below is reconstructed from persisted run
        # state alone. Say so in the prose, not just in the provenance field, because the
        # Markdown/HTML exports travel outside the UI that renders that field.
        summary_parts.append(
            "No agent investigation artifacts were recorded for this run; the report is "
            "reconstructed from persisted events, alerts, and operator activity only."
        )
    executive_summary = " ".join(summary_parts)
    chronology_summary = (
        f"Timeline synthesized from sequences {source.source_sequence_from}"
        f"–{source.source_sequence_to} with {len(source.timeline)} chronology entries."
    )

    created_at = datetime.now(UTC)
    # Content-addressed: the checksum covers what the report *says*, never the randomly
    # allocated report id, so the same run state hashes identically on every regeneration.
    # That is what makes the deterministic fallback auditable and safely re-runnable.
    report_payload = {
        "runId": source.run_id,
        "incidentId": source.incident_id,
        "versionNumber": version_number,
        "generationMode": generation_mode.value,
        "executiveSummary": executive_summary,
        "claims": [claim.model_dump(by_alias=True, mode="json") for claim in claims],
        "timeline": [entry.model_dump(by_alias=True, mode="json") for entry in source.timeline],
    }
    checksum = _checksum(report_payload)

    return AfterActionReportV1(
        schema_version=AFTER_ACTION_REPORT_SCHEMA_VERSION,
        id=report_id,
        run_id=source.run_id,
        incident_id=source.incident_id,
        version_number=version_number,
        title=title,
        executive_summary=executive_summary,
        chronology_summary=chronology_summary,
        claims=claims,
        timeline=source.timeline,
        lessons=[
            "Preserve contradictory evidence in downstream review.",
            "Policy-gated proposals require human approval before execution.",
        ],
        contradictions=contradictions,
        uncertainties=uncertainties,
        source=source,
        grounding_fallback=grounding_fallback,
        generation_mode=generation_mode,
        narrative_provider_id=provider_id,
        narrative_prompt_version=prompt_version,
        session_id=session_id,
        task_id=task_id,
        checksum=checksum,
        created_at=created_at,
    )
