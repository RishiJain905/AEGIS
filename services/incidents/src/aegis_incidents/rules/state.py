"""Run-scoped detection evaluation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DetectionRunState:
    seen_entities: set[str] = field(default_factory=set)
    alert_timestamps: list[tuple[datetime, str, str]] = field(default_factory=list)
    emitted_dedup_keys: set[str] = field(default_factory=set)
    last_alert_by_group: dict[str, tuple[str, datetime]] = field(default_factory=dict)
    prior_auth_failure_burst: dict[str, bool] = field(default_factory=dict)
