"""Server-side fog-of-war redaction for the live WebSocket transport.

The Redis→gateway path forwards the authoritative (fully truthful) domain-event stream. A
player with devtools open must never see attacker-caused state in a raw frame before it is
disclosed, so every operator-bound event passes through :class:`RunDisclosureTracker` at the
gateway's single enqueue choke point. Only ``sim.asset.status_changed`` for an *undisclosed*
governed asset is rewritten — its ``status`` is replaced with the baseline so the client
applies a no-op node delta, keeps its sequence contiguous (no spurious gap/resync), and
learns nothing. Everything else is forwarded verbatim.

Disclosure is run-level (not per-connection). A tracker is seeded from persisted truth on
subscribe and updated incrementally as reveal/alert events flow through the fan-out, so an
already-connected client's *future* events converge; the client converges its *current*
graph by refetching the (serve-time redacted) snapshot when it sees a reveal/alert.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_contracts import DomainEventEnvelopeV1, RealtimeMessageEnvelopeV1
from aegis_simulation_domain import (
    REDACTED_STATUS,
    DisclosureInputs,
    GovernedAsset,
    is_asset_disclosed,
)

_STATUS_CHANGED = "sim.asset.status_changed"
_REVEALED = "sim.hidden_condition.revealed"
_ALERT_PREFIX = "alert."
_RUN_STOPPED = "sim.run.stopped"
_RUN_ACTIVE_EVENTS = frozenset({"sim.run.started", "sim.run.resumed"})


@dataclass
class RunDisclosureTracker:
    """Mutable, run-scoped disclosure state for live redaction."""

    governing_map: dict[str, GovernedAsset]
    revealed_condition_ids: set[str] = field(default_factory=set)
    alerted_asset_ids: set[str] = field(default_factory=set)
    # Fog gating follows the run lifecycle: once the run is terminal the live transport, like
    # the snapshot transport, switches to full ground truth for debrief.
    active: bool = True

    @property
    def has_hidden_state(self) -> bool:
        return bool(self.governing_map)

    def is_disclosed(self, asset_id: str) -> bool:
        return is_asset_disclosed(
            asset_id,
            self.governing_map,
            DisclosureInputs(
                revealed_condition_ids=frozenset(self.revealed_condition_ids),
                alerted_asset_ids=frozenset(self.alerted_asset_ids),
            ),
        )

    def note_event(self, event: DomainEventEnvelopeV1) -> None:
        """Fold a reveal/alert/lifecycle event into disclosure state (idempotent)."""
        if event.type == _REVEALED:
            condition_id = event.payload.get("conditionId")
            if isinstance(condition_id, str):
                self.revealed_condition_ids.add(condition_id)
        elif event.type.startswith(_ALERT_PREFIX):
            asset_id = event.payload.get("assetId")
            if isinstance(asset_id, str) and asset_id:
                self.alerted_asset_ids.add(asset_id)
        elif event.type == _RUN_STOPPED:
            self.active = False
        elif event.type in _RUN_ACTIVE_EVENTS:
            self.active = True

    def redact(self, envelope: RealtimeMessageEnvelopeV1) -> RealtimeMessageEnvelopeV1:
        """Return an operator-safe envelope, rewriting undisclosed status changes only."""
        if not self.has_hidden_state or not self.active:
            return envelope
        event = envelope.event
        if event.type != _STATUS_CHANGED:
            return envelope
        asset_id = event.payload.get("assetId")
        if not isinstance(asset_id, str):
            asset_id = event.subject.id
        if self.is_disclosed(asset_id):
            return envelope
        current_status = event.payload.get("status")
        if current_status == REDACTED_STATUS:
            return envelope
        redacted_event = event.model_copy(
            update={"payload": {**event.payload, "status": REDACTED_STATUS}}
        )
        return envelope.model_copy(update={"event": redacted_event})
