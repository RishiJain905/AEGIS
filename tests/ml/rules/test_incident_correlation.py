"""Deterministic incident correlation (ADR 0037).

Before this existed, a live run produced alerts and no incidents: the only path that could
open a case ran inside WATCHTOWER triage, which the autonomy loop never reached, so BASTION
(whose containment tool requires an open case) was permanently blocked and the after-action
report was empty. These checks are entirely offline — no database, no app, no model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aegis_contracts import (
    ActorRef,
    ActorType,
    AlertV1,
    DomainEventEnvelopeV1,
    IncidentState,
    IncidentV1,
    RunV1,
    deterministic_incident_id,
)
from aegis_contracts.versioning import (
    ALERT_SCHEMA_VERSION,
    DOMAIN_EVENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from aegis_incidents.correlation import (
    DEFAULT_ALERT_THRESHOLD,
    RULE_ALERT_THRESHOLD,
    RULE_COMPROMISE_CONFIRMED,
    compromised_asset_ids,
    correlate_alerts_into_incidents,
    open_correlated_incidents,
)
from aegis_incidents.pipeline import evaluate_features_offline
from aegis_incidents.promotion import candidate_to_alert

_RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_ASSET = "asset:device-workstation-01"
_OTHER_ASSET = "asset:svc-logistics-api"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
#: The run's virtual clock, twelve minutes into the scenario — deliberately not a
#: wall-clock instant, so an event stamped with ``datetime.now()`` is visibly wrong.
_SIM_TIME = datetime(2026, 1, 1, 0, 12, tzinfo=UTC)


def _run() -> RunV1:
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=_RUN,
        scenario_version_id="scenario-version:silent-relay-v1",
        seed=42,
        status="running",
        started_at=_NOW,
        sim_time=_SIM_TIME,
        revision=1,
    )


def _alert(suffix: str, asset_id: str = _ASSET) -> AlertV1:
    return AlertV1(
        schema_version=ALERT_SCHEMA_VERSION,
        id=f"alert:det-{suffix}",
        run_id=_RUN,
        title=f"Rule fired {suffix}",
        severity="high",
        source_event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        asset_id=asset_id,
        created_at=_NOW,
        deduplication_key=f"dedup-{suffix}",
    )


def _status_changed(asset_id: str, status: str) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FBV",
        run_id=_RUN,
        sequence=7,
        type="sim.asset.status_changed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=_NOW,
        recorded_at=_NOW,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation"),
        subject=ActorRef(type=ActorType.ASSET, id=asset_id),
        payload={"assetId": asset_id, "status": status},
        trace_id=_TRACE,
    )


class _FakeIncidentRepository:
    def __init__(self, incidents: list[IncidentV1] | None = None) -> None:
        self.incidents = list(incidents or [])
        self.added: list[IncidentV1] = []
        self.updated: list[IncidentV1] = []

    async def list_by_run(self, run_id: str) -> list[IncidentV1]:
        return [item for item in self.incidents if item.run_id == run_id]

    async def get_by_id(self, incident_id: str) -> IncidentV1 | None:
        return next((item for item in self.incidents if item.id == incident_id), None)

    async def add(self, incident: IncidentV1) -> IncidentV1:
        self.added.append(incident)
        self.incidents.append(incident)
        return incident

    async def update_with_revision(
        self, incident: IncidentV1, *, expected_revision: int
    ) -> IncidentV1:
        assert expected_revision == incident.revision - 1
        self.updated.append(incident)
        self.incidents = [
            incident if item.id == incident.id else item for item in self.incidents
        ]
        return incident


class _FakeAlertRepository:
    def __init__(self, alerts: list[AlertV1]) -> None:
        self._alerts = alerts

    async def list_by_run(self, run_id: str) -> list[AlertV1]:
        return [alert for alert in self._alerts if alert.run_id == run_id]


class _FakeRunRepository:
    """Serves the run's VIRTUAL clock — the value ``sim_time`` on every event must carry."""

    def __init__(self, run: RunV1) -> None:
        self._run = run

    async def get_by_id(self, run_id: str) -> RunV1 | None:
        return self._run if self._run.id == run_id else None


class _FakeUnitOfWork:
    """Records what the correlation step wrote, and how.

    ``append_event`` is the only event path that also inserts the outbox row (the real
    ``EventRepositoryProxy.append`` raises), so asserting the correlation step goes through
    it *is* the atomicity assertion available offline.
    """

    def __init__(self, *, alerts: list[AlertV1], incidents: list[IncidentV1] | None = None):
        self.alerts = _FakeAlertRepository(alerts)
        self.incidents = _FakeIncidentRepository(incidents)
        self.runs = _FakeRunRepository(_run())
        self.appended: list[DomainEventEnvelopeV1] = []
        self.events = _FakeEventRepository(self.appended)

    async def append_event(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1:
        self.appended.append(envelope)
        return envelope


class _FakeEventRepository:
    """Allocates like the real one: the next sequence after everything appended so far."""

    def __init__(self, appended: list[DomainEventEnvelopeV1]) -> None:
        self._appended = appended

    async def next_sequence(self, run_id: str) -> int:
        return max((event.sequence for event in self._appended), default=99) + 1


async def _open(uow: _FakeUnitOfWork, events: list[DomainEventEnvelopeV1]) -> int:
    return await open_correlated_incidents(
        uow,  # type: ignore[arg-type]
        run_id=_RUN,
        events=events,
        trace_id=_TRACE,
    )


def test_an_alert_opens_its_asset_case() -> None:
    result = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=[_alert("a"), _alert("b")],
        compromised_assets=frozenset(),
    )
    assert len(result.opened) == 1
    decision = result.opened[0]
    assert decision.rule_id == RULE_ALERT_THRESHOLD
    assert decision.incident_id == deterministic_incident_id(_RUN, _ASSET)
    assert decision.alert_ids == ("alert:det-a", "alert:det-b")


def test_an_asset_with_no_alert_gets_no_case() -> None:
    """Correlation reads alerts, never the world model — no alert, no case."""
    result = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=[],
        compromised_assets=frozenset({_ASSET}),
    )
    assert result.opened == ()
    assert result.attached == ()


def test_a_raised_threshold_still_holds_a_lone_alert_back() -> None:
    """The threshold is configurable even though Silent Relay is measured at one."""
    result = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=[_alert("a")],
        compromised_assets=frozenset(),
        alert_threshold=2,
    )
    assert result.opened == ()


def test_a_compromised_asset_needs_only_one_corroborating_alert() -> None:
    """The campaign owning the asset is corroboration; waiting for a second rule delays
    the case for no gain."""
    result = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=[_alert("a")],
        compromised_assets=frozenset({_ASSET}),
    )
    assert len(result.opened) == 1
    assert result.opened[0].rule_id == RULE_COMPROMISE_CONFIRMED


def test_a_compromise_detection_never_saw_stays_hidden() -> None:
    """Ground truth alone opens nothing — otherwise the case file would leak fog of war."""
    result = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=[_alert("a", asset_id=_OTHER_ASSET)],
        compromised_assets=frozenset({_ASSET}),
    )
    assert [decision.asset_id for decision in result.opened] == [_OTHER_ASSET]
    assert result.opened[0].rule_id == RULE_ALERT_THRESHOLD


@pytest.mark.asyncio
async def test_a_later_compromise_promotes_the_open_case() -> None:
    """A lead becomes a confirmed intrusion in place, not as a second case."""
    uow = _FakeUnitOfWork(alerts=[_alert("a")])
    await _open(uow, [])
    assert uow.incidents.added[0].title == "Rule fired a"

    opened = await _open(uow, [_status_changed(_ASSET, "compromised")])

    assert opened == 0
    assert len(uow.incidents.added) == 1
    assert uow.incidents.updated[-1].title == f"Confirmed compromise on {_ASSET}"
    assert uow.appended[-1].type == "incident.state_changed"
    assert uow.appended[-1].payload["title"] == f"Confirmed compromise on {_ASSET}"


def test_compromised_assets_are_read_from_the_event_stream() -> None:
    events = [
        _status_changed(_ASSET, "compromised"),
        _status_changed(_OTHER_ASSET, "suspicious"),
    ]
    assert compromised_asset_ids(events) == frozenset({_ASSET})


@pytest.mark.asyncio
async def test_opening_a_case_writes_row_and_event_together() -> None:
    uow = _FakeUnitOfWork(alerts=[_alert("a"), _alert("b")])

    opened = await _open(uow, [])

    assert opened == 1
    assert len(uow.incidents.added) == 1
    incident = uow.incidents.added[0]
    assert incident.state is IncidentState.OPEN
    assert incident.id.startswith("incident:inc_det_")
    assert len(uow.appended) == 1
    event = uow.appended[0]
    assert event.type == "incident.created"
    assert event.sequence == 100
    assert event.actor.id == "asset:detection-engine"
    assert event.actor.type is ActorType.SYSTEM
    # The replay projector rebuilds the row from the payload alone.
    assert event.payload["id"] == incident.id
    assert event.payload["alertIds"] == ["alert:det-a", "alert:det-b"]


@pytest.mark.asyncio
async def test_re_evaluating_the_same_alerts_opens_no_duplicate() -> None:
    """Live detection re-scans the whole run every tick; correlation must be idempotent."""
    alerts = [_alert("a"), _alert("b")]
    uow = _FakeUnitOfWork(alerts=alerts)

    assert await _open(uow, []) == 1
    assert await _open(uow, []) == 0
    assert len(uow.incidents.added) == 1
    assert len(uow.appended) == 1


@pytest.mark.asyncio
async def test_a_follow_on_alert_joins_the_open_case_instead_of_opening_another() -> None:
    uow = _FakeUnitOfWork(alerts=[_alert("a"), _alert("b")])
    await _open(uow, [])

    uow.alerts = _FakeAlertRepository([_alert("a"), _alert("b"), _alert("c")])
    opened = await _open(uow, [])

    assert opened == 0
    assert len(uow.incidents.added) == 1
    assert len(uow.incidents.updated) == 1
    updated = uow.incidents.updated[0]
    assert updated.alert_ids == ["alert:det-a", "alert:det-b", "alert:det-c"]
    assert updated.revision == 1
    attachment_event = uow.appended[-1]
    assert attachment_event.type == "incident.state_changed"
    assert attachment_event.payload["alertIds"] == [
        "alert:det-a",
        "alert:det-b",
        "alert:det-c",
    ]


@pytest.mark.asyncio
async def test_a_second_asset_gets_its_own_case() -> None:
    uow = _FakeUnitOfWork(
        alerts=[
            _alert("a"),
            _alert("b"),
            _alert("c", asset_id=_OTHER_ASSET),
            _alert("d", asset_id=_OTHER_ASSET),
        ]
    )

    assert await _open(uow, []) == 2
    ids = {incident.id for incident in uow.incidents.added}
    assert ids == {
        deterministic_incident_id(_RUN, _ASSET),
        deterministic_incident_id(_RUN, _OTHER_ASSET),
    }
    assert [event.sequence for event in uow.appended] == [100, 101]


def test_identical_inputs_correlate_identically() -> None:
    """Same scenario version + seed must reach the same incident ids in the same order."""
    alerts = [
        _alert("b"),
        _alert("a"),
        _alert("c", asset_id=_OTHER_ASSET),
        _alert("d", asset_id=_OTHER_ASSET),
    ]
    first = correlate_alerts_into_incidents(
        run_id=_RUN, alerts=alerts, compromised_assets=frozenset()
    )
    # Reversed input order — grouping and ordering must not depend on arrival order.
    second = correlate_alerts_into_incidents(
        run_id=_RUN, alerts=list(reversed(alerts)), compromised_assets=frozenset()
    )
    assert first == second
    assert [decision.incident_id for decision in first.opened] == [
        deterministic_incident_id(_RUN, _ASSET),
        deterministic_incident_id(_RUN, _OTHER_ASSET),
    ]


def test_incident_ids_are_run_scoped() -> None:
    other_run = "run_01ARZ3NDEKTSV4RRFFQ69G5FBV"
    assert deterministic_incident_id(_RUN, _ASSET) != deterministic_incident_id(
        other_run, _ASSET
    )


_FIXTURE = Path("scenarios/operation-silent-relay")


def _golden_seeds() -> list[int]:
    import yaml

    registry = yaml.safe_load((_FIXTURE / "golden-seeds.yaml").read_text(encoding="utf-8"))
    return [entry["seed"] for entry in registry["seeds"]]


def _silent_relay_alerts(seed: int = 1000) -> tuple[str, list[AlertV1], list[Any]]:
    from aegis_simulation_domain import SimulationEngine

    manifest = SimulationEngine.load_manifest(_FIXTURE)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=f"scenario-version:{manifest.metadata.version}",
    )
    runtime.start()
    runtime.run_steps(300)
    events = list(runtime.events)
    run_id = events[0].run_id
    pipeline = evaluate_features_offline(run_id=run_id, events=events)
    alerts = [candidate_to_alert(candidate) for candidate in pipeline.accepted_candidates]
    return run_id, alerts, events


@pytest.mark.parametrize("seed", _golden_seeds())
def test_a_silent_relay_run_opens_a_case_with_no_model_in_the_loop(seed: int) -> None:
    """BASTION's containment tool requires an open incident; core CI has no LLM.

    This is the end-to-end offline proof of the ADR 0037 claim: simulation → detection →
    correlation produces a real case with nothing but deterministic code. Every golden
    seed is exercised, because a rule set that only fires on a lucky seed is the same
    failure in a better disguise — an earlier draft (open on two alerts per asset) passed
    on seed 1000 alone and would have shipped five silent runs out of six.
    """
    run_id, alerts, events = _silent_relay_alerts(seed)
    assert alerts, "Silent Relay produced no alerts — detection regressed before correlation"

    result = correlate_alerts_into_incidents(
        run_id=run_id,
        alerts=alerts,
        compromised_assets=compromised_asset_ids(events),
    )
    assert result.opened, (
        "Silent Relay raised alerts but correlated no incident; BASTION would stay blocked"
    )
    for decision in result.opened:
        assert decision.alert_ids
        assert decision.incident_id == deterministic_incident_id(run_id, decision.asset_id)


def test_the_same_seed_correlates_the_same_case_twice() -> None:
    first_run, first_alerts, first_events = _silent_relay_alerts()
    second_run, second_alerts, second_events = _silent_relay_alerts()

    # Run ids are minted per runtime; correlate both against one id so the comparison is
    # about the correlation decisions rather than the identifier they are salted with.
    first = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=first_alerts,
        compromised_assets=compromised_asset_ids(first_events),
    )
    second = correlate_alerts_into_incidents(
        run_id=_RUN,
        alerts=second_alerts,
        compromised_assets=compromised_asset_ids(second_events),
    )
    assert first == second
    assert isinstance(first_run, str) and isinstance(second_run, str)


def test_threshold_default_is_documented() -> None:
    """Measured, not guessed: no Silent Relay asset ever raises two alerts."""
    assert DEFAULT_ALERT_THRESHOLD == 1
