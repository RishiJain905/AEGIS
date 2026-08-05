"""Incident identity and lifecycle event builders.

Incidents are opened from three places that sit in different layers: the detection engine
(deterministic correlation), the WATCHTOWER coordinator in the agent runtime, and the
operator action service in the API. The event payload and the id namespace are therefore
cross-layer contracts, not the property of any one of them — neither of those services may
import the other, so a builder living in either would force a layering inversion or a
second, drifting copy of the ``incident.created`` shape. Both live here, next to the
envelope they build.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aegis_contracts.entities import IncidentV1
from aegis_contracts.events import ActorRef, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION

DETECTION_ENGINE_ACTOR_ID = "asset:detection-engine"


def deterministic_incident_id(run_id: str, correlation_key: str) -> str:
    """The id of the case correlating ``correlation_key`` (an asset id) within a run.

    Pure function of its inputs, so the same scenario + seed opens the same incident ids
    on every replay, and any reader can derive the id of an asset's case without a query.
    Authored ids allow only lowercase ``[a-z0-9._-]`` after the namespace, hence the hex
    digest rather than the raw key.
    """
    digest = hashlib.sha256(f"{run_id}|{correlation_key}".encode()).hexdigest()[:20]
    return f"incident:inc_det_{digest}"


def build_incident_created_event(
    incident: IncidentV1,
    *,
    event_id: str,
    sequence: int,
    actor: ActorRef,
    trace_id: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    """``incident.created`` for a newly opened case.

    Replay, the reports timeline, the after-action dossier, and the realtime ops feed all
    project this event — an incident row written without it is invisible to every one of
    them, and cannot be reconstructed from the event stream at all. ``actor`` varies by
    origin (the detection engine, the triage agent's session, or the operator), so callers
    pass their own.

    The whole incident is carried in the payload, mirroring ``alert.created``, so the
    replay projector rebuilds the row from the event alone rather than from
    ``subject.id`` — which matters because ``ActorType`` has no incident member, so the
    subject can only name the originator, not the case.

    ``sim_time`` is required, not defaulted: it is the run's virtual clock and only the
    caller (which holds the uow) can resolve it via
    ``aegis_persistence.sim_clock.run_sim_time``. A ``datetime.now()`` default is the
    defect this signature exists to prevent — it stamped every case in the chronicle with
    wall-clock time.
    """
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=incident.run_id,
        sequence=sequence,
        type="incident.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=actor,
        subject=actor,
        payload=incident.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
    )


def build_incident_updated_event(
    incident: IncidentV1,
    *,
    event_id: str,
    sequence: int,
    actor: ActorRef,
    trace_id: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    """``incident.state_changed`` for a case whose record moved on.

    Used for correlation attachments as well as state transitions: the event registry has
    exactly two incident types, and a follow-on alert joining an open case still has to
    reach replay somehow. The full incident is the payload for the same reason
    ``incident.created`` carries it — the projector reads ``state`` and ``alertIds`` from
    there, and a row updated without an event silently desynchronises replay.

    ``sim_time`` is required for the same reason as ``incident.created`` above.
    """
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=incident.run_id,
        sequence=sequence,
        type="incident.state_changed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=actor,
        subject=actor,
        payload=incident.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
    )
