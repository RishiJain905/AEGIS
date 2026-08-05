"""``sim_time`` on every domain event is the run's VIRTUAL clock, never wall-clock.

Live QA on the cockpit chronicle showed ``INCIDENT 05:30:33`` interleaved with sim-time
``00:12:00`` entries, operator action cards reading ``05:45:06``, and the CLOCK instrument
flipping to wall time mid-run. Every non-simulation event builder outside
``aegis_agents.runtime.events`` did ``now = datetime.now(UTC)`` and passed ``sim_time=now``
— so a case opened twelve minutes into the scenario was stamped with the wall-clock instant
the transaction committed, roughly 204 days adrift of the alerts that opened it.

The fix is structural, and the tests here pin both halves of it:

* **Behaviour** — the detection engine and the approval workflow, driven against fake
  units of work, stamp their events with the run row's ``sim_time`` and put wall-clock only
  in ``recorded_at``.
* **Structure** — every affected builder takes ``sim_time`` as a *required* keyword-only
  parameter and no builder body reaches for a clock, so a builder cannot silently default
  to ``now()`` again; and every production call site supplies it from something other than
  ``datetime.now``. The structural checks are what cover the builders (operator actions,
  approvals, directives, investigations, reports) whose service paths need a database.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from aegis_agents.autonomy import events as autonomy_events
from aegis_agents.runtime import investigation_events, proposal_events
from aegis_api.approvals import events as approval_events
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_api.directives import events as directive_events
from aegis_api.operator_actions import events as operator_action_events
from aegis_contracts import AlertV1, DomainEventEnvelopeV1, IncidentState, IncidentV1, RunV1
from aegis_contracts import incident_events as contract_incident_events
from aegis_contracts.versioning import (
    ALERT_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from aegis_incidents.correlation import deterministic_incident_id, open_correlated_incidents
from aegis_reports import events as report_events

REPO_ROOT = Path(__file__).resolve().parents[2]

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_LEAD_ASSET = "asset:device-workstation-01"
_FOLLOW_ASSET = "asset:svc-identity-broker"

#: The run's virtual clock: twelve minutes into a scenario whose epoch is 2026-01-01. Far
#: enough from any wall-clock instant that a regression cannot pass by coincidence.
_SIM_TIME = datetime(2026, 1, 1, 0, 12, tzinfo=UTC)


# --------------------------------------------------------------------------------------
# Fakes: enough unit-of-work surface for the two paths under test, and nothing more.
# --------------------------------------------------------------------------------------


class _FakeAlertRepo:
    def __init__(self, alerts: list[AlertV1]) -> None:
        self._alerts = alerts

    async def list_by_run(self, run_id: str) -> list[AlertV1]:
        return [alert for alert in self._alerts if alert.run_id == run_id]


class _FakeIncidentRepo:
    def __init__(self, incidents: list[IncidentV1]) -> None:
        self._incidents = {incident.id: incident for incident in incidents}

    async def list_by_run(self, run_id: str) -> list[IncidentV1]:
        return [i for i in self._incidents.values() if i.run_id == run_id]

    async def get_by_id(self, incident_id: str) -> IncidentV1 | None:
        return self._incidents.get(incident_id)

    async def add(self, incident: IncidentV1) -> IncidentV1:
        self._incidents[incident.id] = incident
        return incident

    async def update_with_revision(
        self, incident: IncidentV1, *, expected_revision: int
    ) -> IncidentV1:
        assert self._incidents[incident.id].revision == expected_revision
        self._incidents[incident.id] = incident
        return incident


class _FakeRunRepo:
    def __init__(self, run: RunV1 | None) -> None:
        self._run = run

    async def get_by_id(self, run_id: str) -> RunV1 | None:
        return self._run if self._run is not None and self._run.id == run_id else None


class _FakeEventRepo:
    def __init__(self) -> None:
        self._next = 1

    async def next_sequence(self, run_id: str) -> int:
        value = self._next
        self._next += 1
        return value


class _FakeUow:
    """Just the repositories the paths under test touch; anything else is a hard failure."""

    def __init__(
        self,
        *,
        run: RunV1 | None,
        alerts: list[AlertV1] | None = None,
        incidents: list[IncidentV1] | None = None,
    ) -> None:
        self.runs = _FakeRunRepo(run)
        self.alerts = _FakeAlertRepo(alerts or [])
        self.incidents = _FakeIncidentRepo(incidents or [])
        self.events = _FakeEventRepo()
        self.appended: list[DomainEventEnvelopeV1] = []

    async def append_event(self, event: DomainEventEnvelopeV1) -> None:
        self.appended.append(event)


def _run(sim_time: datetime = _SIM_TIME) -> RunV1:
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=_RUN_ID,
        scenario_version_id="scenario-version:silent-relay-v1",
        seed=42,
        status="running",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sim_time=sim_time,
        revision=1,
    )


def _alert(alert_id: str, asset_id: str) -> AlertV1:
    return AlertV1(
        schema_version=ALERT_SCHEMA_VERSION,
        id=alert_id,
        run_id=_RUN_ID,
        title=f"Suspicious activity on {asset_id}",
        severity="high",
        source_event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        asset_id=asset_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _open_case(asset_id: str, alert_ids: list[str]) -> IncidentV1:
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=deterministic_incident_id(_RUN_ID, asset_id),
        run_id=_RUN_ID,
        title=f"Existing case on {asset_id}",
        state=IncidentState.OPEN,
        alert_ids=alert_ids,
        revision=0,
        created_at=stamp,
        updated_at=stamp,
    )


# --------------------------------------------------------------------------------------
# Behaviour
# --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detection_engine_stamps_incident_events_with_the_run_sim_clock() -> None:
    """``incident.created`` and ``incident.state_changed`` from the detection engine.

    This is the headline defect: the chronicle showed cases at ``05:30:33`` between
    telemetry rows at ``00:12:00``, because the builder called ``datetime.now(UTC)``.
    """
    uow = _FakeUow(
        run=_run(),
        alerts=[
            _alert("alert:alr_lead0001", _LEAD_ASSET),
            _alert("alert:alr_follow01", _FOLLOW_ASSET),
        ],
        # One asset already has a case, so this single call exercises both the opened
        # branch (incident.created) and the attached branch (incident.state_changed).
        incidents=[_open_case(_FOLLOW_ASSET, [])],
    )
    before = datetime.now(UTC)

    opened = await open_correlated_incidents(
        uow,  # type: ignore[arg-type]
        run_id=_RUN_ID,
        events=[],
        trace_id=_TRACE,
    )

    assert opened == 1
    types = {event.type for event in uow.appended}
    assert types == {"incident.created", "incident.state_changed"}
    for event in uow.appended:
        assert event.sim_time == _SIM_TIME, f"{event.type} carried wall-clock sim_time"
        assert event.recorded_at >= before, f"{event.type} lost its wall-clock recorded_at"
        # The two clocks are months apart in a real run; assert they cannot be conflated.
        assert event.recorded_at - event.sim_time > timedelta(days=1)


@pytest.mark.asyncio
async def test_detection_engine_falls_back_to_wall_clock_only_without_a_run() -> None:
    """The fallback in ``run_sim_time`` is for a missing row, not a silent default."""
    uow = _FakeUow(
        run=None,
        alerts=[_alert("alert:alr_lead0001", _LEAD_ASSET)],
    )
    before = datetime.now(UTC)

    await open_correlated_incidents(
        uow,  # type: ignore[arg-type]
        run_id=_RUN_ID,
        events=[],
        trace_id=_TRACE,
    )

    assert [event.sim_time >= before for event in uow.appended] == [True]


@pytest.mark.asyncio
async def test_approval_transition_stamps_incident_state_changed_with_the_run_sim_clock() -> None:
    """The approval workflow's own ``incident.state_changed`` (a different builder)."""
    incident = _open_case(_LEAD_ASSET, ["alert:alr_lead0001"])
    uow = _FakeUow(run=_run(), incidents=[incident])
    before = datetime.now(UTC)

    await ApprovalWorkflowService()._transition_incident(
        uow,  # type: ignore[arg-type]
        incident_id=incident.id,
        run_id=_RUN_ID,
        new_state=IncidentState.CONTAINING,
        actor_id="agent-session:ags_01arz3ndektsv4rrffq69g5fav",
        trace_id=_TRACE,
    )

    (event,) = uow.appended
    assert event.type == "incident.state_changed"
    assert event.sim_time == _SIM_TIME
    assert event.recorded_at >= before


def test_operator_action_card_carries_the_run_sim_clock() -> None:
    """The event behind the operator action cards that displayed ``05:45:06``."""
    before = datetime.now(UTC)
    event = operator_action_events.build_operator_action_proposed_event(
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        run_id=_RUN_ID,
        sequence=7,
        actor_id="user:operator-alpha",
        trace_id=_TRACE,
        proposal_id="prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        incident_id="incident:inc_op_001",
        scenario_command="isolate",
        action_class="class_2",
        target_asset_id=_LEAD_ASSET,
        justification="Workstation is beaconing; cutting it off.",
        sim_time=_SIM_TIME,
    )

    assert event.type == "operator.action.proposed"
    assert event.sim_time == _SIM_TIME
    assert event.recorded_at >= before


# --------------------------------------------------------------------------------------
# Structure: the defect cannot be reintroduced by a new builder or a new caller.
# --------------------------------------------------------------------------------------

#: Every module holding a domain event builder that previously stamped wall-clock.
_BUILDER_MODULES = [
    contract_incident_events,
    operator_action_events,
    approval_events,
    directive_events,
    investigation_events,
    proposal_events,
    autonomy_events,
    report_events,
]

_BUILDER_NAMES = {
    name
    for module in _BUILDER_MODULES
    for name, obj in vars(module).items()
    if callable(obj) and getattr(obj, "__module__", None) == module.__name__
}


def _envelope_builders() -> list[Any]:
    builders = []
    for module in _BUILDER_MODULES:
        for obj in vars(module).values():
            if not callable(obj) or getattr(obj, "__module__", None) != module.__name__:
                continue
            if inspect.signature(obj).return_annotation != "DomainEventEnvelopeV1":
                continue
            builders.append(obj)
    return builders


def test_every_event_builder_requires_a_sim_time_argument() -> None:
    """Required, not optional-with-a-``now()``-default: the default *was* the bug."""
    builders = _envelope_builders()
    assert len(builders) >= 20, "builder discovery broke; the guard below would pass vacuously"

    for builder in builders:
        parameter = inspect.signature(builder).parameters.get("sim_time")
        where = f"{builder.__module__}.{builder.__qualname__}"
        assert parameter is not None, f"{where} does not take sim_time"
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{where}: sim_time must be keyword-only"
        )
        assert parameter.default is inspect.Parameter.empty, (
            f"{where}: sim_time has a default — a caller that forgets the run's clock must "
            "fail loudly, not fall back to wall-clock"
        )


def _sim_time_arguments(tree: ast.AST) -> list[tuple[str, ast.expr]]:
    """Every ``sim_time=<expr>`` keyword in the tree, tagged with the callee's name."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
        for keyword in node.keywords:
            if keyword.arg == "sim_time":
                found.append((name, keyword.value))
    return found


def _is_now_call(node: ast.expr) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return isinstance(func, ast.Attribute) and func.attr in {"now", "utcnow"}


def test_no_builder_stamps_sim_time_from_a_wall_clock() -> None:
    """Inside a builder, ``sim_time`` may only be the parameter it was handed."""
    for module in _BUILDER_MODULES:
        tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
        for callee, value in _sim_time_arguments(tree):
            where = f"{module.__name__} -> {callee}"
            assert not _is_now_call(value), f"{where}: sim_time stamped from a wall clock"
            assert isinstance(value, ast.Name) and value.id == "sim_time", (
                f"{where}: sim_time must be the caller-supplied parameter, "
                f"got {ast.dump(value)}"
            )


def test_every_production_call_site_supplies_a_non_wall_clock_sim_time() -> None:
    """No caller of these builders may pass ``datetime.now()`` — or omit ``sim_time``."""
    sources = [
        path
        for root in ("apps/api/src", "services", "packages")
        for path in (REPO_ROOT / root).rglob("*.py")
    ]
    assert sources, "source discovery broke"

    checked = 0
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
            if name not in _BUILDER_NAMES or not name.startswith("build_"):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            if "sim_time" not in keywords:
                # Definitions and delegating wrappers re-expose the parameter rather than
                # passing one; a real call site that omits it fails at import-time typing.
                continue
            checked += 1
            assert not _is_now_call(keywords["sim_time"]), (
                f"{path.relative_to(REPO_ROOT)}: {name} stamped with wall-clock time"
            )

    assert checked >= 25, f"only {checked} call sites inspected; the sweep missed callers"
