"""Server-side fog-of-war redaction for the live WebSocket transport.

The Redis→gateway path forwards the authoritative (fully truthful) domain-event stream. A
player with devtools open must never see attacker-caused state in a raw frame before it is
disclosed, so every operator-bound event passes through :class:`RunDisclosureTracker` at the
gateway's single enqueue choke point. Two families are rewritten when they concern an
*undisclosed* governed asset:

* ``sim.asset.status_changed`` has its ``status`` replaced with the baseline, so the client
  applies a no-op node delta.
* ``sim.killchain.*`` — the attacker kill-chain truth markers — have their payload emptied.
  They name the campaign, the ATT&CK technique and the anchor asset outright, which is
  exactly what the player is meant to hunt for, so none of it survives redaction.

Both keep the envelope, and therefore the client's sequence contiguity (no spurious
gap/resync). Everything else is forwarded verbatim. Fog lifts when the run reaches its
win/lose verdict, the same way it lifts when the run stops: once the engagement is decided
the transport switches to ground truth for the debrief.

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
_KILLCHAIN_PREFIX = "sim.killchain."
_OUTCOME_RESOLVED = "sim.run.outcome_resolved"

# Payload fields a kill-chain event uses to name the asset it concerns, most specific first.
_KILLCHAIN_ASSET_FIELDS = ("anchorAssetId", "assetId", "entryAssetId")


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
        elif event.type in {_RUN_STOPPED, _OUTCOME_RESOLVED}:
            self.active = False
        elif event.type in _RUN_ACTIVE_EVENTS:
            self.active = True

    def _redact_killchain(
        self, envelope: RealtimeMessageEnvelopeV1
    ) -> RealtimeMessageEnvelopeV1:
        """Strip an attacker kill-chain marker down to nothing while it is still hidden.

        The payload is emptied rather than partially masked: campaign id, technique id and
        anchor asset each independently give away what the player is hunting, so there is
        no safe subset to keep. The envelope survives only to hold the sequence number.
        """
        event = envelope.event
        referenced = [
            value
            for field in _KILLCHAIN_ASSET_FIELDS
            if isinstance(value := event.payload.get(field), str) and value
        ]
        if not referenced:
            referenced = [event.subject.id]
        if all(self.is_disclosed(asset_id) for asset_id in referenced):
            return envelope
        redacted_event = event.model_copy(
            update={"payload": {"schemaVersion": event.payload.get("schemaVersion", 1)}}
        )
        return envelope.model_copy(update={"event": redacted_event})

    def redact(self, envelope: RealtimeMessageEnvelopeV1) -> RealtimeMessageEnvelopeV1:
        """Return an operator-safe envelope, rewriting only what would leak the attacker."""
        if not self.has_hidden_state or not self.active:
            return envelope
        event = envelope.event
        if event.type.startswith(_KILLCHAIN_PREFIX):
            return self._redact_killchain(envelope)
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
