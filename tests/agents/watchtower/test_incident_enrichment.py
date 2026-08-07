"""A completed triage must leave the case visibly triaged and grounded.

The owner's incident page showed a case the platform had already triaged — timeline
holding only "Alert raised" and "Incident opened", EVIDENCE reading (0), the state badge
still OPEN and the workspace still telling the operator to "triage linked alerts". Two
links were missing behind that, both of which the operator-triggered coordinator had and
the autonomy lane's role handler did not: the case never left OPEN, and the citations the
escalation rested on stayed inside the triage row instead of becoming the case's evidence.

Offline: no database, no provider. The unit of work is a fake and the chain is a stub, so
only the handler's own projections are under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.watchtower.handler import WatchtowerRoleHandler
from aegis_agents.roles.watchtower.incident_state import apply_triage_to_incident
from aegis_contracts import IncidentState, IncidentV1
from aegis_contracts.entities import AgentRole, AutonomyInitiatorV1, RunV1
from aegis_contracts.investigation import (
    EvidenceAttachmentV1,
    EvidenceSourceType,
    TriageEscalationLevel,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import (
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
)

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_INCIDENT_ID = "incident:inc_det_ff3c1988978e876c4b12"
_SESSION_ID = "agent-session:ags_jwawnn54nsjwfkpc3pn8m5qq"
_TASK_ID = "atk_8CF9QF8FF3A5FS1NRWYPCV2CMT"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_EVENT_A = "evt_SKT8CQ38BYXQ9Q37TGMGBC77B7"
_EVENT_B = "evt_MZTDK01186WC3KKRQR86JRF2P3"
_NOW = datetime(2026, 8, 7, 6, 29, tzinfo=UTC)
_SIM_TIME = datetime(2026, 1, 1, 0, 12, tzinfo=UTC)


class _FakeInvestigationRepository:
    def __init__(self) -> None:
        self.triage: list[WatchtowerTriageResultV1] = []
        self.attachments: list[EvidenceAttachmentV1] = []

    async def get_triage_by_idempotency(
        self, _incident_id: str, _key: str
    ) -> WatchtowerTriageResultV1 | None:
        return None

    async def add_triage(self, triage: WatchtowerTriageResultV1) -> WatchtowerTriageResultV1:
        self.triage.append(triage)
        return triage

    async def list_evidence_attachments(self, _incident_id: str) -> list[EvidenceAttachmentV1]:
        return list(self.attachments)

    async def add_evidence_attachment(
        self, attachment: EvidenceAttachmentV1
    ) -> EvidenceAttachmentV1:
        self.attachments.append(attachment)
        return attachment


class _FakeIncidentRepository:
    def __init__(self, incident: IncidentV1 | None) -> None:
        self.incident = incident

    async def get_by_id(self, _incident_id: str) -> IncidentV1 | None:
        return self.incident

    async def update_with_revision(
        self, incident: IncidentV1, *, expected_revision: int
    ) -> IncidentV1:
        assert self.incident is not None
        assert expected_revision == self.incident.revision
        self.incident = incident
        return incident


class _FakeEventRepository:
    def __init__(self) -> None:
        self.sequence = 0

    async def next_sequence(self, _run_id: str) -> int:
        self.sequence += 1
        return self.sequence


class _FakeRunRepository:
    async def get_by_id(self, run_id: str) -> RunV1:
        return RunV1(
            schema_version=RUN_SCHEMA_VERSION,
            id=run_id,
            scenario_version_id="scenario-version:silent-relay-v1",
            seed=7,
            status="running",
            started_at=_NOW,
            sim_time=_SIM_TIME,
            revision=1,
        )


class _FakeUnitOfWork:
    def __init__(self, incident: IncidentV1 | None) -> None:
        self.investigation = _FakeInvestigationRepository()
        self.incidents = _FakeIncidentRepository(incident)
        self.events = _FakeEventRepository()
        self.runs = _FakeRunRepository()
        self.appended: list[Any] = []

    async def append_event(self, event: Any) -> None:
        self.appended.append(event)


class _StubChain:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def advance(self, _uow: object, **kwargs: Any) -> list[str]:
        self.calls.append(kwargs)
        return []


def _incident(state: IncidentState = IncidentState.OPEN, revision: int = 0) -> IncidentV1:
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=_INCIDENT_ID,
        run_id=_RUN_ID,
        title="Unseen source activity detected",
        state=state,
        alert_ids=["alert:det-bd03901f085415dc01cd"],
        revision=revision,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _structured(
    *,
    escalation: str = "monitor",
    citations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """The shape the QA run's one successful autonomous triage actually returned."""
    return {
        "alertSummaries": [],
        "groupedAlertIds": [],
        "separatedAlertIds": [],
        "correlationDecisions": [],
        "escalation": escalation,
        "escalationRationale": "Two successful authentications and nothing corroborating.",
        "confidence": 0.15,
        "evidenceCitations": (
            citations
            if citations is not None
            else [{"evidenceId": _EVENT_A}, {"evidenceId": _EVENT_B}]
        ),
        "toolRequests": [],
    }


def _ctx(uow: _FakeUnitOfWork) -> PostProcessContext:
    return PostProcessContext(
        uow=uow,  # type: ignore[arg-type]
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
        incident_id=_INCIDENT_ID,
        run_id=_RUN_ID,
        trace_id=_TRACE_ID,
        idempotency_key="autonomy-alert:alert:det-bd03901f085415dc01cd-atk_x",
        visible_evidence_ids={_EVENT_A, _EVENT_B},
        initiator=AutonomyInitiatorV1.AUTONOMY,
    )


# --- the citations become the case's evidence ---------------------------------


@pytest.mark.asyncio
async def test_the_grounding_the_escalation_rests_on_becomes_visible_evidence() -> None:
    uow = _FakeUnitOfWork(_incident())
    chain = _StubChain()

    await WatchtowerRoleHandler(chain).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow), structured=_structured()
    )

    assert [item.evidence_id for item in uow.investigation.attachments] == [_EVENT_A, _EVENT_B]
    assert all(
        item.provenance.source_type is EvidenceSourceType.EVENT
        for item in uow.investigation.attachments
    )
    # Each attachment is reported, so replay and the chronicle see it too.
    assert sum(
        1 for event in uow.appended if event.type == "investigation.evidence.attached"
    ) == 2


@pytest.mark.asyncio
async def test_a_monitor_verdict_still_shows_its_working() -> None:
    """MONITOR never chains an investigation, so this projection is the only thing that
    keeps a triaged false positive from rendering as a case nobody looked at."""
    uow = _FakeUnitOfWork(_incident())

    await WatchtowerRoleHandler(_StubChain()).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow), structured=_structured(escalation="monitor")
    )

    assert len(uow.investigation.attachments) == 2


@pytest.mark.asyncio
async def test_a_citation_the_case_already_carries_is_not_stacked_again() -> None:
    """One lane fires a triage per alert against the same case; the panel must not fill
    with the same event repeated."""
    uow = _FakeUnitOfWork(_incident())
    await WatchtowerRoleHandler(_StubChain()).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow), structured=_structured(citations=[{"evidenceId": _EVENT_A}])
    )

    await WatchtowerRoleHandler(_StubChain()).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow),
        structured=_structured(citations=[{"evidenceId": _EVENT_A}, {"evidenceId": _EVENT_B}]),
    )

    assert [item.evidence_id for item in uow.investigation.attachments] == [_EVENT_A, _EVENT_B]


@pytest.mark.asyncio
async def test_a_citation_outside_the_catalogue_is_not_attached() -> None:
    uow = _FakeUnitOfWork(_incident())

    await WatchtowerRoleHandler(_StubChain()).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow),
        structured=_structured(citations=[{"evidenceId": "evt_SKT8CQ38BYXQ9Q37TGMGBC77B6"}]),
    )

    assert uow.investigation.attachments == []


# --- the case moves on --------------------------------------------------------


@pytest.mark.asyncio
async def test_an_autonomously_triaged_case_no_longer_reads_as_untriaged() -> None:
    uow = _FakeUnitOfWork(_incident())

    await WatchtowerRoleHandler(_StubChain()).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow), structured=_structured(escalation="investigate")
    )

    assert uow.incidents.incident is not None
    assert uow.incidents.incident.state is IncidentState.TRIAGED
    assert any(event.type == "incident.state_changed" for event in uow.appended)


@pytest.mark.asyncio
async def test_urgent_triage_opens_the_investigation_phase() -> None:
    uow = _FakeUnitOfWork(_incident())

    await WatchtowerRoleHandler(_StubChain()).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow), structured=_structured(escalation="urgent")
    )

    assert uow.incidents.incident is not None
    assert uow.incidents.incident.state is IncidentState.INVESTIGATING


@pytest.mark.asyncio
async def test_the_chain_is_told_the_verdict_it_must_gate_on() -> None:
    uow = _FakeUnitOfWork(_incident())
    chain = _StubChain()

    await WatchtowerRoleHandler(chain).post_process(  # type: ignore[arg-type]
        ctx=_ctx(uow), structured=_structured(escalation="urgent")
    )

    assert len(chain.calls) == 1
    assert chain.calls[0]["from_role"] is AgentRole.WATCHTOWER
    assert chain.calls[0]["escalation"] is TriageEscalationLevel.URGENT
    assert chain.calls[0]["initiator"] is AutonomyInitiatorV1.AUTONOMY


# --- state only ever moves forward -------------------------------------------


@pytest.mark.asyncio
async def test_a_late_triage_does_not_drag_a_contained_case_backwards() -> None:
    """A lane fires a triage per alert, and alerts keep arriving after BASTION has
    proposed containment. Re-stamping the case TRIAGED would re-open a phase the
    operator has already left."""
    incident = _incident(state=IncidentState.CONTAINMENT_PROPOSED, revision=4)
    uow = _FakeUnitOfWork(incident)

    result = await apply_triage_to_incident(
        uow,  # type: ignore[arg-type]
        incident=incident,
        triage=_triage(TriageEscalationLevel.INVESTIGATE),
        session_id=_SESSION_ID,
        trace_id=_TRACE_ID,
        sim_time=_SIM_TIME,
    )

    assert result.state is IncidentState.CONTAINMENT_PROPOSED
    assert uow.appended == []


@pytest.mark.asyncio
async def test_a_new_alert_still_joins_a_case_that_has_moved_on() -> None:
    """Not advancing the phase is not the same as ignoring the alert."""
    incident = _incident(state=IncidentState.INVESTIGATING, revision=2)
    uow = _FakeUnitOfWork(incident)

    result = await apply_triage_to_incident(
        uow,  # type: ignore[arg-type]
        incident=incident,
        triage=_triage(TriageEscalationLevel.INVESTIGATE),
        session_id=_SESSION_ID,
        trace_id=_TRACE_ID,
        sim_time=_SIM_TIME,
        alert_ids=["alert:det-second"],
    )

    assert result.state is IncidentState.INVESTIGATING
    assert "alert:det-second" in result.alert_ids
    assert uow.appended == []


def _triage(escalation: TriageEscalationLevel) -> WatchtowerTriageResultV1:
    return WatchtowerTriageResultV1(
        schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
        id="wtri_71TFZ2NQWK01YBYFM96HSGN67S",
        incident_id=_INCIDENT_ID,
        run_id=_RUN_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
        alert_summaries=[],
        grouped_alert_ids=[],
        separated_alert_ids=[],
        correlation_decisions=[],
        escalation=escalation,
        escalation_rationale="Correlated.",
        confidence=0.5,
        evidence_ids=[],
        idempotency_key="autonomy-alert:x",
        created_at=_NOW,
    )
