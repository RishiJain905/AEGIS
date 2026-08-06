"""Deterministic assembly of after-action report sources."""

from __future__ import annotations

from aegis_contracts.agent_runtime import AgentTaskV1
from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.reports import AfterActionReportSourceV1
from aegis_contracts.versioning import AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_reports.template import AgentTaskFact
from aegis_reports.timeline import synthesize_timeline


async def assemble_report_source(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    incident_id: str,
) -> tuple[AfterActionReportSourceV1, list[DomainEventEnvelopeV1], list[AgentTaskFact]]:
    incident = await uow.incidents.get_by_id(incident_id)
    if incident is None:
        msg = f"Incident not found: {incident_id}"
        raise KeyError(msg)

    investigation = await uow.investigation.get_detail(incident_id, run_id)
    events = await uow.events.list_by_run(run_id, limit=10_000)
    alerts = await uow.alerts.list_by_run(run_id)

    affected_assets = {
        item.asset_id
        for item in alerts
        if item.asset_id is not None
    }
    for candidate in investigation.candidate_assets:
        affected_assets.add(candidate.asset_id)

    evidence_ids = [
        item.evidence_id
        for item in investigation.evidence_attachments
        if item.evidence_id is not None
    ]
    hypothesis_ids = [item.id for item in investigation.hypotheses]
    proposal_ids = [item.id for item in investigation.proposals]
    policy_decision_ids = [item.id for item in investigation.policy_decisions]
    agent_session_ids = list(
        {
            *[
                item.session_id
                for item in investigation.triage_results
            ],
            *[
                item.session_id
                for item in investigation.plans
            ],
            *[
                item.session_id
                for item in investigation.hypothesis_revisions
            ],
            *[
                item.session_id
                for item in investigation.proposal_revisions
            ],
            *[
                item.session_id
                for item in investigation.policy_decisions
            ],
        }
    )

    # Run-scoped (copilot/lane) sessions carry no incident, so their tasks leave no
    # incident-keyed artifacts for the investigation detail above. They are the
    # AI-teammate interaction the report must still record — without them a run whose
    # copilot completed a triage reads as "no agent investigation artifacts".
    run_scoped_sessions = [
        session for session in await uow.agent_sessions.list_for_run(run_id)
        if session.incident_id is None
    ]
    run_scoped_tasks: list[AgentTaskV1] = []
    for session in run_scoped_sessions:
        run_scoped_tasks.extend(await uow.agent_tasks.list_for_session(session.id))
    terminal_tasks = [
        task
        for task in run_scoped_tasks
        if str(getattr(task, "status", "") or "") in {"completed", "failed", "cancelled"}
    ]
    agent_session_ids = list(
        {*agent_session_ids, *(session.id for session in run_scoped_sessions)}
    )
    agent_task_ids = [task.id for task in terminal_tasks]
    role_by_session = {session.id: str(session.role.value) for session in run_scoped_sessions}
    agent_task_facts = [
        AgentTaskFact(
            task_id=task.id,
            session_id=task.session_id,
            role=role_by_session.get(task.session_id),
            status=str(getattr(task, "status", "") or ""),
            error_message=getattr(task, "error_message", None),
        )
        for task in terminal_tasks
    ]

    sequence_from = events[0].sequence if events else 0
    sequence_to = events[-1].sequence if events else 0
    timeline = synthesize_timeline(events, investigation)

    source = AfterActionReportSourceV1(
        schema_version=AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
        run_id=run_id,
        incident_id=incident_id,
        source_sequence_from=sequence_from,
        source_sequence_to=sequence_to,
        event_ids=[event.event_id for event in events],
        evidence_ids=evidence_ids,
        hypothesis_ids=hypothesis_ids,
        proposal_ids=proposal_ids,
        policy_decision_ids=policy_decision_ids,
        affected_asset_ids=sorted(affected_assets),
        alert_ids=[item.id for item in alerts],
        agent_session_ids=agent_session_ids,
        agent_task_ids=agent_task_ids,
        timeline=timeline,
        investigation_summary={
            "triageCount": len(investigation.triage_results),
            "evidenceAttachmentCount": len(investigation.evidence_attachments),
            "hypothesisCount": len(investigation.hypotheses),
            "proposalCount": len(investigation.proposals),
            "policyDecisionCount": len(investigation.policy_decisions),
            "agentTaskCount": len(agent_task_facts),
            "incidentState": incident.state.value,
            "incidentTitle": incident.title,
        },
    )
    return source, events, agent_task_facts
