"""Structured errors for deterministic scoring."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_contracts.scoring import ScoreErrorCode


@dataclass
class ScoringError(Exception):
    code: ScoreErrorCode
    message: str
    trace_id: str | None = None
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message
