"""Deterministic incident correlation.

Incidents are opened by the detection layer, not by an agent. Alerts fire from
transparent rules; when a run's alerts cross a correlation threshold on an asset, the case
is opened in the same transaction that persisted the alerts — row, ``incident.created``
event and outbox entry together.

Why here and not in WATCHTOWER triage: incident existence is core simulation flow. The
model-driven path made it provider-coupled, so a local-model outage produced a run with
alerts, no incidents, a blocked BASTION (its containment tool needs an open case) and an
empty after-action report. Core CI must pass without an external LLM (architecture §20), so
the thing every downstream subsystem depends on cannot be behind a model call. WATCHTOWER
still triages — it enriches the case that already exists rather than conjuring it. See ADR
0037.

Every decision here is a pure function of the persisted alert set and the run's event
stream, so the same scenario version and seed correlate the same alerts into the same
incident ids in the same order. ``deterministic_incident_id`` derives the id from
``(run_id, asset_id)``, which is also what makes dedupe free: an asset's case can only be
opened once, and any reader can derive it without a query.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from aegis_contracts import (
    DETECTION_ENGINE_ACTOR_ID,
    ActorRef,
    ActorType,
    AlertV1,
    DomainEventEnvelopeV1,
    IncidentState,
    IncidentV1,
    build_incident_created_event,
    build_incident_updated_event,
    deterministic_incident_id,
)
from aegis_contracts.versioning import INCIDENT_SCHEMA_VERSION
from aegis_persistence.sim_clock import run_sim_time
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_incidents.promotion import deterministic_event_id

CORRELATION_RULESET_VERSION = "1.0.0"

#: Distinct alerts on one asset that open its case. One, because that is what Operation
#: Silent Relay actually produces: measured over all six golden seeds to the full live
#: horizon (1500 sim-seconds), every run raises exactly three alerts and never more than
#: **one per asset**. A threshold of two would have opened zero cases on five of six seeds
#: — including runs the attacker wins by exfiltration — which is precisely the failure this
#: correlation exists to end. The grouping work is still real and still transparent: the
#: case is keyed to the asset, so every later alert on it joins that case instead of
#: spawning another, and an alert is by definition the detection layer asserting that
#: something on this asset warrants investigation.
DEFAULT_ALERT_THRESHOLD = 1

#: Asset statuses the simulation writes when a campaign technique lands. A compromised
#: asset that detection has *also* alerted on is a confirmed intrusion rather than a lead,
#: so its case says so. Ground truth alone never opens a case — that would hand the
#: operator a compromise detection never found and collapse the scenario's fog of war.
COMPROMISE_STATUSES = frozenset({"compromised"})

RULE_ALERT_THRESHOLD = "correlation-alert-threshold"
RULE_COMPROMISE_CONFIRMED = "correlation-compromise-confirmed"

_STATUS_CHANGED_EVENT = "sim.asset.status_changed"


@dataclass(frozen=True)
class IncidentCorrelationDecision:
    """One case the correlation rules say should exist, and why."""

    incident_id: str
    asset_id: str
    title: str
    alert_ids: tuple[str, ...]
    rule_id: str
    rationale: str


@dataclass(frozen=True)
class IncidentAttachment:
    """An update to a case that is already open for an asset.

    Either follow-on alerts joining it, or — when the simulation compromises an asset whose
    case was opened on a lead alone — the promotion of that case to a confirmed compromise.
    """

    incident_id: str
    asset_id: str
    alert_ids: tuple[str, ...]
    title: str | None = None


@dataclass(frozen=True)
class IncidentCorrelationResult:
    opened: tuple[IncidentCorrelationDecision, ...] = ()
    attached: tuple[IncidentAttachment, ...] = ()


def compromised_asset_ids(events: list[DomainEventEnvelopeV1]) -> frozenset[str]:
    """Assets the simulation has taken to a compromised status.

    Read from the event stream rather than the world model so correlation stays a pure
    function of persisted history — the same input events always yield the same set, on a
    live run and on a replay alike.
    """
    compromised: set[str] = set()
    for event in events:
        if event.type != _STATUS_CHANGED_EVENT:
            continue
        payload = event.payload
        status = payload.get("status")
        if not isinstance(status, str) or status not in COMPROMISE_STATUSES:
            continue
        asset_id = payload.get("assetId")
        if isinstance(asset_id, str) and asset_id:
            compromised.add(asset_id)
    return frozenset(compromised)


def _compromise_title(asset_id: str) -> str:
    return f"Confirmed compromise on {asset_id}"


def _incident_title(asset_id: str, alerts: list[AlertV1], rule_id: str) -> str:
    if rule_id == RULE_COMPROMISE_CONFIRMED:
        return _compromise_title(asset_id)
    if len(alerts) == 1:
        return alerts[0].title
    return f"Correlated activity on {asset_id} ({len(alerts)} alerts)"


def correlate_alerts_into_incidents(
    *,
    run_id: str,
    alerts: list[AlertV1],
    compromised_assets: frozenset[str],
    known_incidents: dict[str, IncidentV1] | None = None,
    alert_threshold: int = DEFAULT_ALERT_THRESHOLD,
) -> IncidentCorrelationResult:
    """Decide which cases a run's alerts warrant. Pure — no I/O, no clock, no randomness.

    ``known_incidents`` are the run's already-open detection cases, keyed by id. An asset
    whose case exists is never opened twice; its follow-on alerts (and a later compromise
    confirmation) are reported in ``attached`` instead, which is what keeps one campaign
    from fanning out into a queue of near-duplicate cases.
    """
    known = known_incidents or {}
    by_asset: dict[str, list[AlertV1]] = {}
    for alert in alerts:
        by_asset.setdefault(alert.asset_id, []).append(alert)

    opened: list[IncidentCorrelationDecision] = []
    attached: list[IncidentAttachment] = []
    for asset_id in sorted(by_asset):
        # Alert ids are content-derived (``deterministic_alert_id``), so sorting by id is
        # stable across runs in a way that ``created_at`` — a wall clock — is not.
        asset_alerts = sorted(by_asset[asset_id], key=lambda item: item.id)
        alert_ids = tuple(alert.id for alert in asset_alerts)
        incident_id = deterministic_incident_id(run_id, asset_id)

        compromised = asset_id in compromised_assets
        compromise_title = _compromise_title(asset_id)

        existing = known.get(incident_id)
        if existing is not None:
            # A case opened on a lead is promoted once the campaign confirms it, so the
            # queue distinguishes "something looks off here" from "the attacker owns this".
            promoted = compromised and existing.title != compromise_title
            if set(alert_ids) - set(existing.alert_ids) or promoted:
                attached.append(
                    IncidentAttachment(
                        incident_id=incident_id,
                        asset_id=asset_id,
                        alert_ids=alert_ids,
                        title=compromise_title if promoted else None,
                    )
                )
            continue

        if compromised:
            rule_id = RULE_COMPROMISE_CONFIRMED
            rationale = (
                f"Asset reached a compromised status with {len(alert_ids)} corroborating "
                "alert(s) already raised on it."
            )
        elif len(asset_alerts) >= alert_threshold:
            rule_id = RULE_ALERT_THRESHOLD
            rationale = (
                f"{len(alert_ids)} distinct alerts fired on the same asset "
                f"(threshold {alert_threshold})."
            )
        else:
            continue

        opened.append(
            IncidentCorrelationDecision(
                incident_id=incident_id,
                asset_id=asset_id,
                title=_incident_title(asset_id, asset_alerts, rule_id),
                alert_ids=alert_ids,
                rule_id=rule_id,
                rationale=rationale,
            )
        )

    return IncidentCorrelationResult(opened=tuple(opened), attached=tuple(attached))


def _detection_actor() -> ActorRef:
    return ActorRef(type=ActorType.SYSTEM, id=DETECTION_ENGINE_ACTOR_ID)


async def open_correlated_incidents(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
    trace_id: str,
    alert_threshold: int = DEFAULT_ALERT_THRESHOLD,
) -> int:
    """Open (and top up) the run's correlated cases. Returns incidents opened.

    Runs inside the caller's transaction so every incident row lands with its
    ``incident.created`` event and outbox entry, per the architecture contract. Attaching
    a follow-on alert emits ``incident.state_changed`` for the same reason: replay rebuilds
    incidents from events, so a silently updated row desynchronises it.

    Sequences come from ``events.next_sequence`` rather than arithmetic on ``events``:
    that list is whatever slice the caller evaluated, and the detection route may pass a
    subset, so ``max(slice) + 1`` can name a sequence that already exists and lose the
    whole transaction to a duplicate-event error.
    """
    alerts = await uow.alerts.list_by_run(run_id)
    if not alerts:
        return 0
    by_id = {incident.id: incident for incident in await uow.incidents.list_by_run(run_id)}

    result = correlate_alerts_into_incidents(
        run_id=run_id,
        alerts=alerts,
        compromised_assets=compromised_asset_ids(events),
        known_incidents=by_id,
        alert_threshold=alert_threshold,
    )
    if not result.opened and not result.attached:
        return 0

    now = datetime.now(UTC)
    # The run's VIRTUAL clock, not ``now``: a case that the chronicle timestamps at
    # wall-clock sorts nowhere near the alerts that opened it. ``created_at`` on the row
    # stays wall-clock; only the event's ``sim_time`` is the simulation instant.
    sim_now = await run_sim_time(uow, run_id)
    for decision in result.opened:
        incident = IncidentV1(
            schema_version=INCIDENT_SCHEMA_VERSION,
            id=decision.incident_id,
            run_id=run_id,
            title=decision.title,
            state=IncidentState.OPEN,
            alert_ids=list(decision.alert_ids),
            revision=0,
            created_at=now,
            updated_at=now,
        )
        created = await uow.incidents.add(incident)
        await uow.append_event(
            build_incident_created_event(
                created,
                event_id=deterministic_event_id(f"incident:{decision.incident_id}"),
                sequence=await uow.events.next_sequence(run_id),
                actor=_detection_actor(),
                trace_id=trace_id,
                sim_time=sim_now,
            )
        )

    for attachment in result.attached:
        incident = by_id[attachment.incident_id]
        merged = sorted({*incident.alert_ids, *attachment.alert_ids})
        updated = await uow.incidents.update_with_revision(
            incident.model_copy(
                update={
                    "alert_ids": merged,
                    "title": attachment.title or incident.title,
                    "revision": incident.revision + 1,
                    "updated_at": now,
                }
            ),
            expected_revision=incident.revision,
        )
        await uow.append_event(
            build_incident_updated_event(
                updated,
                # Content-addressed on exactly what changed, so a rolled-back transaction
                # re-emits an identical event rather than a colliding or duplicate one.
                event_id=deterministic_event_id(
                    f"incident-update:{attachment.incident_id}:"
                    f"{','.join(merged)}:{updated.title}"
                ),
                sequence=await uow.events.next_sequence(run_id),
                actor=_detection_actor(),
                trace_id=trace_id,
                sim_time=sim_now,
            )
        )

    return len(result.opened)
