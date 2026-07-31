"""Run-scoped detection evaluation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DetectionRunState:
    seen_entities: set[str] = field(default_factory=set)
    alert_timestamps: list[tuple[datetime, str, str]] = field(default_factory=list)
    emitted_dedup_keys: set[str] = field(default_factory=set)
    # Keyed by (suppression group, entity id): a suppression group exists to stop one
    # asset's noise from becoming an alert storm, not to hide a second asset. Keyed by
    # group alone it did exactly that — in Operation Silent Relay the first
    # ``rule-unseen-source`` alert suppressed the identical rule firing on the campaign's
    # compromised identity broker, leaving the run with a single alert on an unrelated
    # asset and nothing for incident correlation to build a case from.
    last_alert_by_group: dict[tuple[str, str], tuple[str, datetime]] = field(
        default_factory=dict
    )
    prior_auth_failure_burst: dict[str, bool] = field(default_factory=dict)
