"""Scoring facts assembler — multi-incident aggregation.

The debrief's decision timeline must see every executed operator action. Operator
direct actions anchor to the deterministic operator incident (``incident:inc_op_<run>``,
created lazily on the first action), which is usually NOT the oldest incident — the
alert-opened case is. The assembler therefore aggregates proposals / approvals /
executed actions across EVERY incident in the run, deduped by id, and resolves an
operator approval's sequence from the ``action.executed`` event (operator direct
actions emit no ``action.proposal.approved``).

Fully offline: the unit of work is faked, so no PostgreSQL is touched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from aegis_contracts.entities import (
    ActionClass,
    ActionProposalV1,
    ApprovalDecision,
    ApprovalV1,
    ExecutedActionV1,
    IncidentState,
    IncidentV1,
    ProposalStatus,
)
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    APPROVAL_SCHEMA_VERSION,
    EXECUTED_ACTION_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    INVESTIGATION_DETAIL_SCHEMA_VERSION,
)
from aegis_scoring.assembler import assemble_scoring_facts

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
ALERT_INCIDENT_ID = "incident:inc_alert_001"
OPERATOR_INCIDENT_ID = "incident:inc_op_001"
OPERATOR_SESSION_ID = "agent-session:operator-console"
PROPOSAL_ID = "prp_01ARZ3NDEKTSV4RRFFQ69G5FB9"
APPROVAL_ID = "apr_01ARZ3NDEKTSV4RRFFQ69G5FBA"
ACTION_ID = "act_01ARZ3NDEKTSV4RRFFQ69G5FBB"
EXECUTED_SEQUENCE = 252


def _now() -> datetime:
    return datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def _incident(incident_id: str, created_at: datetime) -> IncidentV1:
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=incident_id,
        run_id=RUN_ID,
        title="Suspicious relay beaconing",
        state=IncidentState.OPEN,
        alert_ids=[],
        created_at=created_at,
        updated_at=created_at,
        revision=1,
    )


def _proposal(*, incident_id: str, session_id: str) -> ActionProposalV1:
    return ActionProposalV1(
        schema_version=ACTION_PROPOSAL_SCHEMA_VERSION,
        id=PROPOSAL_ID,
        incident_id=incident_id,
        agent_session_id=session_id,
        action_class=ActionClass.OPERATIONAL,
        target_asset_id="asset:svc-identity-broker",
        command="isolate_service",
        scenario_command="isolate_service",
        current_revision_id="prv_01ARZ3NDEKTSV4RRFFQ69G5FBC",
        status=ProposalStatus.EXECUTED,
        rationale="Confirmed compromise on Identity Broker at SEQ 107; isolate now.",
        revision=3,
        created_at=_now(),
    )


def _approval() -> ApprovalV1:
    return ApprovalV1(
        schema_version=APPROVAL_SCHEMA_VERSION,
        id=APPROVAL_ID,
        proposal_id=PROPOSAL_ID,
        decision=ApprovalDecision.APPROVED,
        approver_id="user-admin-alpha",
        proposal_revision=2,
        decided_at=_now(),
    )


def _executed_action() -> ExecutedActionV1:
    return ExecutedActionV1(
        schema_version=EXECUTED_ACTION_SCHEMA_VERSION,
        id=ACTION_ID,
        proposal_id=PROPOSAL_ID,
        run_id=RUN_ID,
        result_event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FBD",
        idempotency_key="op-action-1",
        executed_at=_now(),
    )


def _event(
    sequence: int,
    event_type: str,
    *,
    payload: dict[str, Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        event_id=f"evt_{sequence:04d}",
        run_id=RUN_ID,
        sequence=sequence,
        type=event_type,
        payload=payload or {},
        subject=SimpleNamespace(id="asset:svc-identity-broker"),
        sim_time=None,
    )


class _FakeRuns:
    async def get_by_id(self, run_id: str) -> Any:
        return (
            SimpleNamespace(
                id=RUN_ID,
                scenario_version_id="scenario-version:silent-relay-1",
                status="completed",
            )
            if run_id == RUN_ID
            else None
        )


class _FakeScenarioVersions:
    async def get_by_id(self, scenario_version_id: str) -> Any:
        return SimpleNamespace(
            scenario_id="scenario:operation-silent-relay",
            version="1.0.0",
        )


class _FakeEvents:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def list_by_run(self, run_id: str, limit: int = 0) -> list[Any]:
        return self._events


class _FakeIncidents:
    def __init__(self, incidents: list[IncidentV1]) -> None:
        self._incidents = incidents

    async def list_by_run(self, run_id: str) -> list[IncidentV1]:
        return [item for item in self._incidents if item.run_id == run_id]


class _FakeEvidence:
    async def list_for_run(self, run_id: str) -> list[Any]:
        return []


class _FakeAlerts:
    async def list_by_run(self, run_id: str) -> list[Any]:
        return []


class _FakeReports:
    async def list_versions(self, run_id: str) -> list[Any]:
        return []


class _FakeInvestigation:
    def __init__(self, details: dict[str, InvestigationDetailV1]) -> None:
        self._details = details

    async def get_detail(
        self, incident_id: str, run_id: str
    ) -> InvestigationDetailV1:
        return self._details.get(incident_id, _empty_detail(incident_id))


def _empty_detail(incident_id: str) -> InvestigationDetailV1:
    return InvestigationDetailV1(
        schema_version=INVESTIGATION_DETAIL_SCHEMA_VERSION,
        incident_id=incident_id,
        run_id=RUN_ID,
    )


class _FakeUow:
    def __init__(
        self,
        *,
        incidents: list[IncidentV1],
        details: dict[str, InvestigationDetailV1],
        events: list[Any],
    ) -> None:
        self.runs = _FakeRuns()
        self.scenario_versions = _FakeScenarioVersions()
        self.events = _FakeEvents(events)
        self.incidents = _FakeIncidents(incidents)
        self.evidence = _FakeEvidence()
        self.alerts = _FakeAlerts()
        self.reports = _FakeReports()
        self.investigation = _FakeInvestigation(details)


def _operator_run_facts() -> Any:
    """A run where the operator executed Isolate via the console command bar.

    The operator incident is created lazily on the first action, so it is the SECOND
    incident; the alert-opened case is the first. The operator path emits only
    ``action.executed`` (no ``action.proposal.approved``), carrying the approvalId.
    """
    alert_incident = _incident(ALERT_INCIDENT_ID, _now())
    operator_incident = _incident(OPERATOR_INCIDENT_ID, _now())
    operator_detail = _empty_detail(OPERATOR_INCIDENT_ID).model_copy(
        update={
            "proposals": [_proposal(
                incident_id=OPERATOR_INCIDENT_ID,
                session_id=OPERATOR_SESSION_ID,
            )],
            "approvals": [_approval()],
            "executed_actions": [_executed_action()],
        }
    )
    events = [
        _event(
            EXECUTED_SEQUENCE,
            "action.executed",
            payload={
                "proposalId": PROPOSAL_ID,
                "approvalId": APPROVAL_ID,
                "executedActionId": ACTION_ID,
            },
        )
    ]
    return _FakeUow(
        incidents=[alert_incident, operator_incident],
        details={OPERATOR_INCIDENT_ID: operator_detail},
        events=events,
    )


@pytest.mark.asyncio
async def test_operator_direct_action_survives_multi_incident_aggregation() -> None:
    """The executed Isolate on the operator incident reaches the scoring facts."""
    facts = await assemble_scoring_facts(_operator_run_facts(), run_id=RUN_ID)

    assert facts.incident_id == ALERT_INCIDENT_ID  # primary anchor stays the oldest
    assert len(facts.proposals) == 1
    assert facts.proposals[0].agent_session_id == OPERATOR_SESSION_ID
    assert len(facts.approvals) == 1
    # The operator path emits no action.proposal.approved; the sequence must come
    # from the action.executed event or the debrief timeline misplaces the decision.
    assert facts.approvals[0].sequence == EXECUTED_SEQUENCE
    assert len(facts.executed_actions) == 1
    assert facts.executed_actions[0].sequence == EXECUTED_SEQUENCE
    assert facts.executed_actions[0].target_asset_ids == ("asset:svc-identity-broker",)


@pytest.mark.asyncio
async def test_approver_authorized_approval_uses_proposal_event_sequence() -> None:
    """An agent proposal approved by an approver keeps its action.proposal.approved seq."""
    alert_incident = _incident(ALERT_INCIDENT_ID, _now())
    detail = _empty_detail(ALERT_INCIDENT_ID).model_copy(
        update={
            "proposals": [_proposal(
                incident_id=ALERT_INCIDENT_ID,
                session_id="agent-session:ags_bastion_001",
            )],
            "approvals": [_approval()],
            "executed_actions": [_executed_action()],
        }
    )
    events = [
        _event(
            100,
            "action.proposal.approved",
            payload={"proposalId": PROPOSAL_ID, "approvalId": APPROVAL_ID},
        ),
        _event(
            105,
            "action.executed",
            payload={"proposalId": PROPOSAL_ID, "approvalId": APPROVAL_ID},
        ),
    ]
    uow = _FakeUow(
        incidents=[alert_incident],
        details={ALERT_INCIDENT_ID: detail},
        events=events,
    )

    facts = await assemble_scoring_facts(uow, run_id=RUN_ID)

    assert len(facts.approvals) == 1
    assert facts.approvals[0].sequence == 100
    assert facts.executed_actions[0].sequence == 105
    assert facts.proposals[0].agent_session_id == "agent-session:ags_bastion_001"


@pytest.mark.asyncio
async def test_artifacts_shared_across_incidents_are_deduped() -> None:
    """The same proposal/approval/action appearing in two details is counted once."""
    alert_incident = _incident(ALERT_INCIDENT_ID, _now())
    operator_incident = _incident(OPERATOR_INCIDENT_ID, _now())
    shared_detail = _empty_detail(ALERT_INCIDENT_ID).model_copy(
        update={
            "proposals": [_proposal(
                incident_id=ALERT_INCIDENT_ID,
                session_id=OPERATOR_SESSION_ID,
            )],
            "approvals": [_approval()],
            "executed_actions": [_executed_action()],
        }
    )
    uow = _FakeUow(
        incidents=[alert_incident, operator_incident],
        details={ALERT_INCIDENT_ID: shared_detail},
        events=[
            _event(
                EXECUTED_SEQUENCE,
                "action.executed",
                payload={"proposalId": PROPOSAL_ID, "approvalId": APPROVAL_ID},
            )
        ],
    )

    facts = await assemble_scoring_facts(uow, run_id=RUN_ID)

    assert len(facts.proposals) == 1
    assert len(facts.approvals) == 1
    assert len(facts.executed_actions) == 1


@pytest.mark.asyncio
async def test_run_without_incidents_has_no_artifacts() -> None:
    uow = _FakeUow(incidents=[], details={}, events=[])

    facts = await assemble_scoring_facts(uow, run_id=RUN_ID)

    assert facts.incident_id is None
    assert facts.proposals == []
    assert facts.approvals == []
    assert facts.executed_actions == []
