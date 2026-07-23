"""Live WebSocket fog-of-war redaction (RunDisclosureTracker) unit tests.

Offline — exercises the gateway's per-run redaction choke point without Redis/DB.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_api.websocket.disclosure import RunDisclosureTracker
from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION
from aegis_event_streaming.envelope import build_realtime_envelope
from aegis_simulation_domain import GovernedAsset

_RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_ASSET = "asset:svc-file-server"
_CONDITION = "hidden-cause-phishing-compromise"


def _event(event_type: str, payload: dict, *, sequence: int = 5, subject: str = _ASSET):
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    return DomainEventEnvelopeV1(
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
        run_id=_RUN,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=subject),
        payload={"schemaVersion": 1, **payload},
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
    )


def _tracker(**kwargs) -> RunDisclosureTracker:
    governing = {_ASSET: GovernedAsset(_ASSET, frozenset({_CONDITION}), 0.1, "normal")}
    return RunDisclosureTracker(governing_map=governing, **kwargs)


def _status_envelope(status: str):
    return build_realtime_envelope(
        _event("sim.asset.status_changed", {"assetId": _ASSET, "status": status})
    )


def test_undisclosed_status_change_is_redacted():
    tracker = _tracker()
    redacted = tracker.redact(_status_envelope("compromised"))
    assert redacted.event.payload["status"] == "normal"
    # Sequence and identity are preserved so the client stays contiguous (no gap/resync).
    assert redacted.event.sequence == 5
    assert redacted.event.event_id == "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW"


def test_reveal_event_converges_future_frames_to_truth():
    tracker = _tracker()
    assert tracker.redact(_status_envelope("compromised")).event.payload["status"] == "normal"
    tracker.note_event(_event("sim.hidden_condition.revealed", {"conditionId": _CONDITION}))
    # After the reveal the same asset's status changes pass through unredacted.
    assert tracker.redact(_status_envelope("compromised")).event.payload["status"] == "compromised"


def test_alert_event_discloses_asset():
    tracker = _tracker()
    tracker.note_event(_event("alert.created", {"assetId": _ASSET, "title": "x"}))
    assert tracker.redact(_status_envelope("suspicious")).event.payload["status"] == "suspicious"


def test_ungoverned_asset_never_redacted():
    tracker = _tracker()
    env = build_realtime_envelope(
        _event(
            "sim.asset.status_changed",
            {"assetId": "asset:svc-identity-provider", "status": "compromised"},
            subject="asset:svc-identity-provider",
        )
    )
    assert tracker.redact(env).event.payload["status"] == "compromised"


def test_non_status_events_pass_through():
    tracker = _tracker()
    env = build_realtime_envelope(_event("telemetry.network.connection", {"assetId": _ASSET}))
    assert tracker.redact(env) is env


def test_terminal_run_shows_truth():
    tracker = _tracker()
    tracker.note_event(_event("sim.run.stopped", {}))
    # Post-run: the live transport, like the snapshot transport, switches to ground truth.
    assert tracker.redact(_status_envelope("compromised")).event.payload["status"] == "compromised"
