"""Assemble ScoringFacts from PostgreSQL unit of work + scenario content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis_contracts.scoring import ScoreErrorCode
from aegis_persistence.mappers import incident_to_domain
from aegis_persistence.orm.tables import IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select

from aegis_scoring.errors import ScoringError
from aegis_scoring.facts import (
    ApprovalFact,
    EventFact,
    EvidenceFact,
    ExecutedActionFact,
    HypothesisFact,
    ProposalFact,
    ScoringFacts,
)
from aegis_scoring.rubric_loader import (
    build_rubric_from_manifest,
    load_expected_evidence,
    load_objectives,
    load_response_branches,
    load_yaml,
    resolve_scenario_dir,
)


def _event_asset_id(payload: dict[str, Any], subject_id: str | None = None) -> str | None:
    for key in ("assetId", "asset_id", "targetAssetId", "entityId"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    if subject_id and subject_id.startswith("asset:"):
        return subject_id
    return None


async def assemble_scoring_facts(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    scenarios_root: Path | None = None,
    incident_id: str | None = None,
) -> ScoringFacts:
    run = await uow.runs.get_by_id(run_id)
    if run is None:
        raise ScoringError(
            code=ScoreErrorCode.SCORE_VALIDATION_FAILED,
            message=f"Run not found: {run_id}",
            details={"runId": run_id},
        )

    scenario_version = await uow.scenario_versions.get_by_id(run.scenario_version_id)
    scenario_id = scenario_version.scenario_id if scenario_version else "scenario:unknown"
    scenario_ver = scenario_version.version if scenario_version else "0.0.0"

    scenario_dir = resolve_scenario_dir(scenario_id, scenarios_root=scenarios_root)
    if scenario_dir is None:
        raise ScoringError(
            code=ScoreErrorCode.SCORE_RUBRIC_MISSING,
            message=f"Scenario content not found for {scenario_id}",
            details={"scenarioId": scenario_id},
        )

    manifest = load_yaml(scenario_dir / "manifest.yaml")
    rubric = build_rubric_from_manifest(manifest)
    expected = load_expected_evidence(scenario_dir / "expected-evidence.yaml")
    objectives = load_objectives(manifest)
    response_branches = load_response_branches(manifest)

    cause_labels: dict[str, str] = {}
    expected_yaml = load_yaml(scenario_dir / "expected-evidence.yaml")
    for cause_key, cause in (expected_yaml.get("causes") or {}).items():
        cause_labels[str(cause_key)] = str(cause.get("label") or cause_key)

    events_raw = await uow.events.list_by_run(run_id, limit=10_000)
    event_facts: list[EventFact] = []
    true_cause_id: str | None = None
    selected_response_branch: str | None = None

    for envelope in events_raw:
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        subject_id = getattr(envelope.subject, "id", None)
        event_facts.append(
            EventFact(
                event_id=envelope.event_id,
                sequence=envelope.sequence,
                event_type=envelope.type,
                asset_id=_event_asset_id(payload, subject_id),
                sim_time=str(envelope.sim_time) if envelope.sim_time else None,
                payload=payload,
            )
        )
        if envelope.type == "sim.branch.selected":
            branch_id = str(payload.get("branchId") or payload.get("branch_id") or "")
            group = str(payload.get("branchGroup") or payload.get("branch_group") or "")
            if group == "root-cause" or branch_id.startswith("hidden-cause"):
                true_cause_id = branch_id or true_cause_id
            if branch_id.startswith("branch-response"):
                selected_response_branch = branch_id
        if envelope.type in {"sim.hidden_condition.revealed", "sim.hidden_condition.triggered"}:
            condition_id = str(
                payload.get("conditionId")
                or payload.get("hiddenCauseId")
                or payload.get("condition_id")
                or ""
            )
            if condition_id.startswith("hidden-cause"):
                true_cause_id = condition_id

    # Resolve incident
    resolved_incident_id = incident_id
    if resolved_incident_id is None:
        assert uow._session is not None  # noqa: SLF001
        result = await uow._session.execute(  # noqa: SLF001
            select(IncidentRow)
            .where(IncidentRow.run_id == run_id)
            .order_by(IncidentRow.created_at.asc())
        )
        row = result.scalars().first()
        if row is not None:
            resolved_incident_id = incident_to_domain(row).id

    evidence_rows = await uow.evidence.list_for_run(run_id)
    evidence_facts = [
        EvidenceFact(
            evidence_id=row.id,
            source_event_id=row.source_event_id,
            asset_id=row.asset_id,
            summary=row.summary,
            created_sequence=None,
        )
        for row in evidence_rows
    ]

    hypothesis_facts: list[HypothesisFact] = []
    proposal_facts: list[ProposalFact] = []
    approval_facts: list[ApprovalFact] = []
    executed_facts: list[ExecutedActionFact] = []
    affected: set[str] = {ev.asset_id for ev in evidence_facts if ev.asset_id}

    if resolved_incident_id is not None:
        detail = await uow.investigation.get_detail(resolved_incident_id, run_id)
        for hyp in detail.hypotheses:
            hypothesis_facts.append(
                HypothesisFact(
                    hypothesis_id=hyp.id,
                    statement=hyp.statement or "",
                    confidence=hyp.confidence,
                    status=hyp.status,
                    revision=1,
                    created_sequence=None,
                )
            )
        policy_by_proposal = {
            d.proposal_id: str(d.outcome.value if hasattr(d.outcome, "value") else d.outcome)
            for d in detail.policy_decisions
            if getattr(d, "proposal_id", None)
        }
        for prop in detail.proposals:
            action_class = (
                prop.action_class.value
                if hasattr(prop.action_class, "value")
                else str(prop.action_class)
            )
            status = prop.status.value if hasattr(prop.status, "value") else str(prop.status)
            proposal_facts.append(
                ProposalFact(
                    proposal_id=prop.id,
                    action_class=action_class,
                    status=status,
                    summary=prop.rationale or prop.command,
                    target_asset_ids=(prop.target_asset_id,),
                    created_sequence=None,
                    policy_decision=policy_by_proposal.get(prop.id),
                )
            )
            affected.add(prop.target_asset_id)

        for approval in detail.approvals:
            decision = (
                approval.decision.value
                if hasattr(approval.decision, "value")
                else str(approval.decision)
            )
            seq = 0
            for event in event_facts:
                if event.event_type in {
                    "action.proposal.approved",
                    "action.proposal.rejected",
                    "action.proposal.modified",
                    "action.proposal.cancelled",
                } and (
                    event.payload.get("proposalId") == approval.proposal_id
                    or event.payload.get("approvalId") == approval.id
                ):
                    seq = event.sequence
                    break
            approval_facts.append(
                ApprovalFact(
                    approval_id=approval.id,
                    proposal_id=approval.proposal_id,
                    decision=decision,
                    sequence=seq,
                    decided_at=str(approval.decided_at) if approval.decided_at else None,
                )
            )

        for action in detail.executed_actions:
            impact = 0.5
            summary = str(getattr(action, "result_summary", "") or "").lower()
            if "high" in summary or "disrupt" in summary:
                impact = 0.85
            elif "low" in summary or "minimal" in summary:
                impact = 0.25
            seq = 0
            for event in event_facts:
                if event.event_type == "action.executed" and (
                    event.payload.get("proposalId") == action.proposal_id
                    or event.payload.get("actionId") == action.id
                ):
                    seq = event.sequence
                    break
            target_ids: tuple[str, ...] = ()
            matching_prop = next(
                (p for p in proposal_facts if p.proposal_id == action.proposal_id), None
            )
            if matching_prop:
                target_ids = matching_prop.target_asset_ids
            executed_facts.append(
                ExecutedActionFact(
                    action_id=action.id,
                    proposal_id=action.proposal_id,
                    sequence=seq,
                    outcome=str(getattr(action, "result_summary", "") or "executed"),
                    impact_score=impact,
                    target_asset_ids=target_ids,
                )
            )

    alerts = await uow.alerts.list_by_run(run_id)
    for alert in alerts:
        if alert.asset_id:
            affected.add(alert.asset_id)
        # Represent alerts as synthetic event facts for detection scoring when alert events absent
        event_facts.append(
            EventFact(
                event_id=alert.source_event_id,
                sequence=max((e.sequence for e in event_facts), default=0),
                event_type="alert.created",
                asset_id=alert.asset_id,
                sim_time=None,
                payload={"alertId": alert.id, "title": alert.title},
            )
        )

    scribe_report_id = None
    scribe_version_number = None
    lessons: list[str] = []
    versions = await uow.reports.list_versions(run_id)
    if versions:
        latest = versions[-1]
        scribe_report_id = latest.report_id
        scribe_version_number = latest.version_number
        report = await uow.reports.get_report(run_id, version_number=latest.version_number)
        if report is not None:
            lessons = list(report.lessons)

    return ScoringFacts(
        run_id=run_id,
        run_status=str(run.status),
        scenario_id=scenario_id,
        scenario_version=str(scenario_ver),
        rubric=rubric,
        events=sorted(event_facts, key=lambda e: e.sequence),
        evidence=evidence_facts,
        hypotheses=hypothesis_facts,
        proposals=proposal_facts,
        approvals=approval_facts,
        executed_actions=executed_facts,
        expected_evidence=expected,
        objectives=objectives,
        response_branches=response_branches,
        true_cause_id=true_cause_id,
        true_cause_label=cause_labels.get(true_cause_id or ""),
        selected_response_branch=selected_response_branch,
        incident_id=resolved_incident_id,
        affected_asset_ids=sorted(affected),
        lessons=lessons,
        scribe_report_id=scribe_report_id,
        scribe_version_number=scribe_version_number,
    )
