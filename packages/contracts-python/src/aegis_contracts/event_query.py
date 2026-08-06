"""Shared event-search matching for the operator console and the agent tools.

The Evidence tab and the agents' ``search_events`` tool must agree on what an
event is and when it matches a query: the copilot's citations are only
verifiable if both surfaces search the same pool the same way. This module is
that one implementation — the console service and the agent tool handler both
delegate here, so a filter added for one is a filter added for both.

The text haystack deliberately includes the event id: the copilot cites
``evt_...`` ids from the evidence catalogue, and the operator must be able to
paste a cited id into Evidence and find the event that carries it.
"""

from __future__ import annotations

from datetime import datetime

from aegis_contracts.events import DomainEventEnvelopeV1

#: Payload keys that name the asset an event is about, in priority order.
_ASSET_PAYLOAD_KEYS = ("assetId", "targetAssetId", "sourceAssetId")


def event_asset_id(event: DomainEventEnvelopeV1) -> str | None:
    """The asset an event is about, or ``None`` when it names none.

    Mirrors the operator-facing asset attribution: payload keys first, then the
    envelope's subject when it is an asset. Both surfaces must attribute the
    same asset to the same event, or an asset-filtered search would disagree
    with the Evidence tab.
    """
    for key in _ASSET_PAYLOAD_KEYS:
        value = event.payload.get(key)
        if isinstance(value, str) and value:
            return value
    subject_id = event.subject.id
    if isinstance(subject_id, str) and subject_id.startswith("asset:"):
        return subject_id
    return None


def event_evidence_summary(event: DomainEventEnvelopeV1) -> str:
    """One-line summary of an event for the evidence catalogue.

    The type is the discriminator the model picks ids by; the sim time and
    asset make the entry identifiable against the Evidence tab, which shows the
    same three fields.
    """
    asset = event_asset_id(event)
    base = f"{event.type} @ {event.sim_time.isoformat()}"
    return f"{base} [{asset}]" if asset else base


def event_matches_filters(
    event: DomainEventEnvelopeV1,
    *,
    asset_id: str | None = None,
    event_type_prefix: str | None = None,
    text: str | None = None,
    from_sim_time: datetime | None = None,
    to_sim_time: datetime | None = None,
) -> bool:
    """Whether an event matches a console/agent search query.

    Every filter is optional; an event matches when it satisfies all the
    filters that were given. ``text`` matches the event id, type, and payload
    (case-insensitive), so a cited ``evt_...`` id is a valid search.
    """
    if event_type_prefix and not event.type.startswith(event_type_prefix):
        return False
    if asset_id and event_asset_id(event) != asset_id:
        return False
    if from_sim_time is not None and event.sim_time < from_sim_time:
        return False
    if to_sim_time is not None and event.sim_time > to_sim_time:
        return False
    if text is not None:
        haystack = f"{event.event_id} {event.type} {event.payload}".lower()
        if text.lower() not in haystack:
            return False
    return True
