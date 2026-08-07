"""Moving a case forward when triage lands.

Shared by both triage paths — :class:`WatchtowerCoordinator` (operator-triggered) and
:class:`WatchtowerRoleHandler` (the autonomy lane) — because a case that has been triaged
is triaged regardless of who asked. Only the coordinator did this before, so an
autonomously triaged incident sat at OPEN forever and the workspace kept telling the
operator to "triage linked alerts" for a case the platform had already triaged.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from aegis_contracts import IncidentState, IncidentV1
from aegis_contracts.investigation import TriageEscalationLevel, WatchtowerTriageResultV1
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.proposal_events import build_incident_state_changed_event

# How far along the response a state sits. Triage may only move a case forward: a second
# triage turn arriving after BASTION proposed containment must not drag the case back to
# TRIAGED and re-open a phase the operator has already left.
_PROGRESSION: dict[IncidentState, int] = {
    IncidentState.OPEN: 0,
    IncidentState.TRIAGED: 1,
    IncidentState.INVESTIGATING: 2,
    IncidentState.CONTAINMENT_PROPOSED: 3,
    IncidentState.APPROVAL_PENDING: 4,
    IncidentState.CONTAINING: 5,
    IncidentState.MONITORING: 6,
    IncidentState.RESOLVED: 7,
    IncidentState.CLOSED: 8,
}


def triage_target_state(escalation: TriageEscalationLevel) -> IncidentState:
    """Urgent triage opens the investigation phase; anything else marks the case triaged."""
    if escalation is TriageEscalationLevel.URGENT:
        return IncidentState.INVESTIGATING
    return IncidentState.TRIAGED


async def apply_triage_to_incident(
    uow: PostgresUnitOfWork,
    *,
    incident: IncidentV1,
    triage: WatchtowerTriageResultV1,
    session_id: str,
    trace_id: str,
    sim_time: datetime,
    alert_ids: Iterable[str] = (),
) -> IncidentV1:
    """Record the case's new state and the event that reports it, in one transaction.

    Returns the incident as persisted — unchanged when triage found nothing to advance,
    which is the common case for a case already under investigation.
    """
    merged_alert_ids = sorted({*incident.alert_ids, *alert_ids})
    target = triage_target_state(escalation=triage.escalation)
    advances = _PROGRESSION[target] > _PROGRESSION[incident.state]
    if not advances and merged_alert_ids == list(incident.alert_ids):
        return incident

    next_state = target if advances else incident.state
    updated = await uow.incidents.update_with_revision(
        incident.model_copy(
            update={
                "alert_ids": merged_alert_ids,
                "state": next_state,
                "revision": incident.revision + 1,
                "updated_at": datetime.now(UTC),
            }
        ),
        expected_revision=incident.revision,
    )
    if advances:
        # Row and event in the same transaction, per the architecture contract: replay,
        # the chronicle and the after-action dossier reconstruct incident state from the
        # event stream, and would otherwise never see the case leave OPEN.
        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_incident_state_changed_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                session_id=session_id,
                trace_id=trace_id,
                incident_id=incident.id,
                previous_state=incident.state.value,
                new_state=next_state.value,
                sim_time=sim_time,
            )
        )
    return updated
