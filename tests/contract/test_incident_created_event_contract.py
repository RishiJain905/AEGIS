"""Every incident creation site must emit ``incident.created``.

The QA run ``run_8024W2GZ4PMQ02P8FXTH840AY6`` held an incident row but its 1101-event
history contained zero ``incident.created`` events, because none of the production
creation paths appended one — the only emitter in the codebase was the database seed.
Replay (``aegis_replay.projectors``), the reports timeline, the after-action dossier, and
the web ops feed all reconstruct incidents *from the event stream*, so those cases were
invisible to every one of them and unrecoverable by replay.

These checks are offline: they build the event directly and read the creation sites'
source, no database and no app.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_api.operator_actions.service import OperatorActionService
from aegis_contracts import (
    ActorRef,
    ActorType,
    IncidentState,
    IncidentV1,
    build_incident_created_event,
)
from aegis_contracts.versioning import INCIDENT_SCHEMA_VERSION
from aegis_incidents.correlation import open_correlated_incidents

_RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


@pytest.fixture
def incident() -> IncidentV1:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id="incident:inc_contract_001",
        run_id=_RUN,
        title="Correlated incident (3 alerts)",
        state=IncidentState.OPEN,
        alert_ids=["alert:a", "alert:b", "alert:c"],
        revision=0,
        created_at=now,
        updated_at=now,
    )


def _event(incident: IncidentV1):
    return build_incident_created_event(
        incident,
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        sequence=42,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:detection-engine"),
        trace_id=_TRACE,
    )


def test_event_is_typed_and_anchored_to_the_run(incident: IncidentV1) -> None:
    event = _event(incident)
    assert event.type == "incident.created"
    assert event.run_id == _RUN
    assert event.sequence == 42


def test_payload_carries_everything_the_replay_projector_reads(incident: IncidentV1) -> None:
    """``_on_incident_created`` rebuilds the row from the payload, not from ``subject.id``.

    ``ActorType`` has no incident member, so the subject can only name the originator —
    the payload is the sole source of the incident's identity and contents.
    """
    payload = _event(incident).payload
    assert payload["id"] == incident.id
    assert payload["title"] == incident.title
    assert payload["state"] == IncidentState.OPEN.value
    assert payload["alertIds"] == ["alert:a", "alert:b", "alert:c"]


def test_agent_and_operator_origins_are_distinguishable(incident: IncidentV1) -> None:
    """After-action attribution depends on telling autonomous triage from an operator."""
    system = _event(incident)
    operator = build_incident_created_event(
        incident,
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FBV",
        sequence=43,
        actor=ActorRef(type=ActorType.OPERATOR, id="user:operator-alpha"),
        trace_id=_TRACE,
    )
    assert system.actor.type == ActorType.SYSTEM
    assert operator.actor.type == ActorType.OPERATOR


def test_watchtower_triage_appends_the_event_with_the_row() -> None:
    """A row written without its event is invisible to replay — assert they travel together."""
    import inspect

    source = inspect.getsource(WatchtowerCoordinator._resolve_incident)
    assert "uow.incidents.add(incident)" in source
    assert "build_incident_created_event(" in source
    assert "uow.append_event(" in source


def test_operator_incident_appends_the_event_with_the_row() -> None:
    import inspect

    source = inspect.getsource(OperatorActionService._ensure_operator_incident)
    assert "uow.incidents.add(incident)" in source
    assert "build_incident_created_event(" in source
    assert "uow.append_event(" in source


def test_deterministic_correlation_appends_the_event_with_the_row() -> None:
    """The detection engine is the primary creation site now (ADR 0037) — same rule."""
    import inspect

    source = inspect.getsource(open_correlated_incidents)
    assert "uow.incidents.add(incident)" in source
    assert "build_incident_created_event(" in source
    assert "uow.append_event(" in source


def test_hypothesis_listing_cannot_open_an_incident() -> None:
    """A read path must not reach the creating branch now that creation emits an event."""
    import inspect

    source = inspect.getsource(OperatorActionService.list_hypotheses)
    assert "_require_incident(" in source
    assert "_resolve_incident(" not in source
