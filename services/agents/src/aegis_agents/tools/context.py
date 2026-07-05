"""Shared tool execution context."""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_persistence.unit_of_work import PostgresUnitOfWork


@dataclass
class ToolExecutionContext:
    uow: PostgresUnitOfWork
    session_id: str
    task_id: str
    incident_id: str
    run_id: str
    trace_id: str
    visible_evidence_ids: set[str] = field(default_factory=set)
