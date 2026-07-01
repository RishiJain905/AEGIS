"""Normalized deterministic event history hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from aegis_contracts import DomainEventEnvelopeV1
from aegis_contracts.simulation import NormalizedEventHashV1
from aegis_contracts.versioning import NORMALIZED_EVENT_HASH_SCHEMA_VERSION


def _normalize_envelope(envelope: DomainEventEnvelopeV1) -> dict[str, Any]:
    data = envelope.model_dump(mode="json", by_alias=True)
    data.pop("eventId", None)
    data.pop("recordedAt", None)
    data.pop("traceId", None)
    return data


def compute_normalized_event_hash(
    *,
    events: list[DomainEventEnvelopeV1],
    scenario_version_id: str,
    seed: int,
    engine_version: str,
) -> NormalizedEventHashV1:
    normalized = [
        _normalize_envelope(event) for event in sorted(events, key=lambda item: item.sequence)
    ]
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return NormalizedEventHashV1(
        schema_version=NORMALIZED_EVENT_HASH_SCHEMA_VERSION,
        scenario_version_id=scenario_version_id,
        seed=seed,
        engine_version=engine_version,
        hash_value=f"sha256:{digest}",
        event_count=len(events),
    )


def checkpoint_checksum(world_state_payload: dict[str, Any]) -> str:
    canonical = json.dumps(world_state_payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"
