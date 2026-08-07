"""Autonomous turns must hand the case to the next role.

The owner's P1: an incident detail page whose timeline held only "Alert raised" and
"Incident opened", whose EVIDENCE read (0), and whose RESPONSE PROPOSALS read
"No proposals". Every one of those panels is fed by an artifact whose only producer was a
role that ran downstream of WATCHTOWER — and the autonomy lane never enqueued one. The
rules-of-engagement prose already promised the operator otherwise ("you MAY chain a single
follow-up TRACE investigation"), but chaining creates agent sessions, which is deliberately
not a model-visible tool, so the promise had no mechanism behind it.

Offline: no database, no provider. The unit of work, the session service and the task
service are fakes; the follow-up idempotency guard is exercised through the compiled
statement's bind parameters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.roles.chaining import InvestigationChain
from aegis_agents.runtime.ids import new_agent_session_id, new_runtime_id
from aegis_contracts import RulesOfEngagementV1
from aegis_contracts.agent_runtime import AgentTaskStatus, AgentTaskV1
from aegis_contracts.entities import (
    AgentRole,
    AgentSessionState,
    AgentSessionV1,
    AutonomyInitiatorV1,
    RunLoadoutV1,
    RunV1,
)
from aegis_contracts.investigation import TriageEscalationLevel
from aegis_contracts.versioning import (
    AGENT_SESSION_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_INCIDENT_ID = "incident:inc_det_ff3c1988978e876c4b12"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_NOW = datetime(2026, 8, 7, 6, 28, tzinfo=UTC)


class _Result:
    def __init__(self, hit: bool) -> None:
        self._hit = hit

    def first(self) -> tuple[str] | None:
        return ("atk_existing",) if self._hit else None


class _FakeSession:
    """Answers the stage-guard query by reading the statement's own bind values."""

    def __init__(self, existing_keys: set[str]) -> None:
        self._existing = existing_keys

    async def execute(self, statement: Any) -> _Result:
        bound = {
            value for value in statement.compile().params.values() if isinstance(value, str)
        }
        return _Result(bool(bound & self._existing))


class _FakeRunRepository:
    def __init__(self, run: RunV1 | None) -> None:
        self._run = run

    async def get_by_id(self, run_id: str) -> RunV1 | None:
        return self._run if self._run is not None and self._run.id == run_id else None


class _FakeInvestigationRepository:
    def __init__(self, evidence_count: int) -> None:
        self._evidence = [object()] * evidence_count

    async def list_evidence_attachments(self, _incident_id: str) -> list[object]:
        return list(self._evidence)


class _FakeOracleRepository:
    def __init__(self, hypothesis_count: int) -> None:
        self._hypotheses = [object()] * hypothesis_count

    async def list_hypotheses_for_incident(self, _incident_id: str) -> list[object]:
        return list(self._hypotheses)


class _FakeUnitOfWork:
    def __init__(
        self,
        *,
        roe: RulesOfEngagementV1 | None = RulesOfEngagementV1.INVESTIGATE,
        existing_keys: set[str] | None = None,
        evidence_count: int = 0,
        hypothesis_count: int = 0,
    ) -> None:
        self.session = _FakeSession(existing_keys or set())
        self.runs = _FakeRunRepository(_run(roe))
        self.investigation = _FakeInvestigationRepository(evidence_count)
        self.oracle_hypotheses = _FakeOracleRepository(hypothesis_count)


def _run(roe: RulesOfEngagementV1 | None) -> RunV1:
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=_RUN_ID,
        scenario_version_id="scenario-version:silent-relay-v1",
        seed=7,
        status="running",
        started_at=_NOW,
        sim_time=_NOW,
        revision=1,
        loadout=None if roe is None else RunLoadoutV1(roe=roe),
    )


class _RecordingSessionService:
    def __init__(self) -> None:
        self.roles: list[AgentRole] = []
        self.origins: list[AutonomyInitiatorV1] = []

    async def create_session(
        self,
        _uow: object,
        *,
        incident_id: str,
        request: Any,
        origin: AutonomyInitiatorV1 = AutonomyInitiatorV1.OPERATOR,
    ) -> AgentSessionV1:
        self.roles.append(request.role)
        self.origins.append(origin)
        return AgentSessionV1(
            schema_version=AGENT_SESSION_SCHEMA_VERSION,
            id=new_agent_session_id(),
            run_id=_RUN_ID,
            incident_id=incident_id,
            role=request.role,
            state=AgentSessionState.QUEUED,
            trace_id=request.trace_id,
            origin=origin,
            created_at=_NOW,
            updated_at=_NOW,
        )


class _RecordingTaskService:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self.initiators: list[AutonomyInitiatorV1] = []

    async def create_task(
        self,
        _uow: object,
        *,
        session: AgentSessionV1,
        request: Any,
        incident_id: str | None = None,
    ) -> AgentTaskV1:
        self.keys.append(request.idempotency_key)
        self.initiators.append(request.initiator)
        return AgentTaskV1(
            schema_version=AGENT_TASK_SCHEMA_VERSION,
            id=new_runtime_id("atk"),
            session_id=session.id,
            run_id=session.run_id,
            incident_id=incident_id or session.incident_id,
            status=AgentTaskStatus.QUEUED,
            attempt=1,
            idempotency_key=request.idempotency_key,
            trace_id=session.trace_id,
            provider_id="openai-compatible",
            initiator=request.initiator,
            created_at=_NOW,
            updated_at=_NOW,
        )


def _chain() -> tuple[InvestigationChain, _RecordingSessionService, _RecordingTaskService]:
    sessions = _RecordingSessionService()
    tasks = _RecordingTaskService()
    return (
        InvestigationChain(sessions=sessions, tasks=tasks),  # type: ignore[arg-type]
        sessions,
        tasks,
    )


async def _advance(
    chain: InvestigationChain,
    uow: _FakeUnitOfWork,
    *,
    from_role: AgentRole,
    initiator: AutonomyInitiatorV1 = AutonomyInitiatorV1.AUTONOMY,
    escalation: TriageEscalationLevel | None = None,
) -> list[str]:
    return await chain.advance(
        uow,  # type: ignore[arg-type]
        from_role=from_role,
        incident_id=_INCIDENT_ID,
        run_id=_RUN_ID,
        trace_id=_TRACE_ID,
        initiator=initiator,
        escalation=escalation,
    )


# --- WATCHTOWER -> TRACE ------------------------------------------------------


@pytest.mark.asyncio
async def test_an_escalated_triage_opens_the_investigation_that_fills_the_case() -> None:
    chain, sessions, tasks = _chain()
    uow = _FakeUnitOfWork()

    enqueued = await _advance(
        chain,
        uow,
        from_role=AgentRole.WATCHTOWER,
        escalation=TriageEscalationLevel.INVESTIGATE,
    )

    assert len(enqueued) == 1
    assert sessions.roles == [AgentRole.TRACE]
    # The lane's own marking: these threads are background initiative, not operator chat.
    assert sessions.origins == [AutonomyInitiatorV1.AUTONOMY]
    assert tasks.initiators == [AutonomyInitiatorV1.AUTONOMY]
    assert tasks.keys == [f"autonomy-chain:{_INCIDENT_ID}:trace"]


@pytest.mark.asyncio
async def test_a_monitor_verdict_does_not_investigate_itself() -> None:
    """MONITOR is triage concluding there is nothing here; investigating anyway would
    contradict the finding, and it is the gate the operator path already applies."""
    chain, sessions, _ = _chain()

    enqueued = await _advance(
        chain,
        _FakeUnitOfWork(),
        from_role=AgentRole.WATCHTOWER,
        escalation=TriageEscalationLevel.MONITOR,
    )

    assert enqueued == []
    assert sessions.roles == []


@pytest.mark.asyncio
async def test_observe_reports_and_never_chains() -> None:
    chain, sessions, _ = _chain()

    enqueued = await _advance(
        chain,
        _FakeUnitOfWork(roe=RulesOfEngagementV1.OBSERVE),
        from_role=AgentRole.WATCHTOWER,
        escalation=TriageEscalationLevel.URGENT,
    )

    assert enqueued == []
    assert sessions.roles == []


@pytest.mark.asyncio
async def test_a_run_without_a_loadout_still_investigates() -> None:
    """Pre-loadout runs default to INVESTIGATE, exactly as the poller reads them."""
    chain, sessions, _ = _chain()

    enqueued = await _advance(
        chain,
        _FakeUnitOfWork(roe=None),
        from_role=AgentRole.WATCHTOWER,
        escalation=TriageEscalationLevel.INVESTIGATE,
    )

    assert len(enqueued) == 1
    assert sessions.roles == [AgentRole.TRACE]


@pytest.mark.asyncio
async def test_operator_tasked_turns_leave_chaining_to_the_coordinators() -> None:
    """The operator path enqueues its own follow-ups. Chaining here too would double
    every investigation, and would let the ORACLE coordinator's TRACE follow-up
    ping-pong against this."""
    chain, sessions, _ = _chain()

    enqueued = await _advance(
        chain,
        _FakeUnitOfWork(),
        from_role=AgentRole.WATCHTOWER,
        initiator=AutonomyInitiatorV1.OPERATOR,
        escalation=TriageEscalationLevel.URGENT,
    )

    assert enqueued == []
    assert sessions.roles == []


@pytest.mark.asyncio
async def test_a_second_triage_on_the_same_case_does_not_open_a_second_investigation() -> None:
    """The guard is keyed on the incident and the stage, not the turn: one lane fires a
    triage per alert, and a case with six alerts must still get one TRACE."""
    chain, sessions, _ = _chain()
    uow = _FakeUnitOfWork(existing_keys={f"autonomy-chain:{_INCIDENT_ID}:trace"})

    enqueued = await _advance(
        chain,
        uow,
        from_role=AgentRole.WATCHTOWER,
        escalation=TriageEscalationLevel.URGENT,
    )

    assert enqueued == []
    assert sessions.roles == []


# --- TRACE -> ORACLE ----------------------------------------------------------


@pytest.mark.asyncio
async def test_collected_evidence_hands_the_case_to_oracle() -> None:
    chain, sessions, tasks = _chain()

    enqueued = await _advance(
        chain,
        _FakeUnitOfWork(evidence_count=3),
        from_role=AgentRole.TRACE,
    )

    assert len(enqueued) == 1
    assert sessions.roles == [AgentRole.ORACLE]
    assert tasks.keys == [f"autonomy-chain:{_INCIDENT_ID}:oracle"]


@pytest.mark.asyncio
async def test_oracle_is_not_asked_to_hypothesise_about_nothing() -> None:
    chain, sessions, _ = _chain()

    enqueued = await _advance(chain, _FakeUnitOfWork(evidence_count=0), from_role=AgentRole.TRACE)

    assert enqueued == []
    assert sessions.roles == []


# --- ORACLE -> BASTION + WARDEN ----------------------------------------------


@pytest.mark.asyncio
async def test_forward_deployed_drafts_a_response_and_its_policy_reading() -> None:
    chain, sessions, tasks = _chain()
    uow = _FakeUnitOfWork(roe=RulesOfEngagementV1.FORWARD_DEPLOYED, hypothesis_count=2)

    enqueued = await _advance(chain, uow, from_role=AgentRole.ORACLE)

    assert len(enqueued) == 2
    assert sessions.roles == [AgentRole.BASTION, AgentRole.WARDEN]
    assert tasks.keys == [
        f"autonomy-chain:{_INCIDENT_ID}:bastion",
        f"autonomy-chain:{_INCIDENT_ID}:bastion-warden",
    ]


@pytest.mark.asyncio
async def test_investigate_stops_short_of_drafting_containment() -> None:
    """Drafting a response is the one step INVESTIGATE withholds, per its own prompt."""
    chain, sessions, _ = _chain()
    uow = _FakeUnitOfWork(roe=RulesOfEngagementV1.INVESTIGATE, hypothesis_count=2)

    enqueued = await _advance(chain, uow, from_role=AgentRole.ORACLE)

    assert enqueued == []
    assert sessions.roles == []


@pytest.mark.asyncio
async def test_no_hypotheses_means_the_case_is_not_ready_for_a_response() -> None:
    """``BastionCoordinator`` raises on this precondition; a background chain treats it
    as "not yet" rather than enqueueing a turn that would fail on arrival."""
    chain, sessions, _ = _chain()
    uow = _FakeUnitOfWork(roe=RulesOfEngagementV1.FORWARD_DEPLOYED, hypothesis_count=0)

    enqueued = await _advance(chain, uow, from_role=AgentRole.ORACLE)

    assert enqueued == []
    assert sessions.roles == []


@pytest.mark.asyncio
async def test_warden_is_not_queued_alone_when_bastion_was_already_drafted() -> None:
    chain, sessions, _ = _chain()
    uow = _FakeUnitOfWork(
        roe=RulesOfEngagementV1.FORWARD_DEPLOYED,
        hypothesis_count=2,
        existing_keys={f"autonomy-chain:{_INCIDENT_ID}:bastion"},
    )

    enqueued = await _advance(chain, uow, from_role=AgentRole.ORACLE)

    assert enqueued == []
    assert sessions.roles == []


@pytest.mark.asyncio
async def test_a_run_scoped_turn_has_no_case_to_advance() -> None:
    """Autonomy leaves a task run-scoped when the asset has no open case yet (ADR 0037);
    there is nothing to chain onto."""
    chain, sessions, _ = _chain()

    enqueued = await chain.advance(
        _FakeUnitOfWork(),  # type: ignore[arg-type]
        from_role=AgentRole.WATCHTOWER,
        incident_id="",
        run_id=_RUN_ID,
        trace_id=_TRACE_ID,
        initiator=AutonomyInitiatorV1.AUTONOMY,
        escalation=TriageEscalationLevel.URGENT,
    )

    assert enqueued == []
    assert sessions.roles == []
