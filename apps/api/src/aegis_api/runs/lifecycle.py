"""Run lifecycle cohesion — after-action artifacts produced when a run stops.

A run stops one of two ways: the operator issues ``POST /runs/{id}/stop`` or the tick
engine reaches the scenario's completion horizon. Both call :func:`finalize_stopped_run`
so a stopped run always ends with a score (and, when a full investigation exists, an
after-action report). Finalization is strictly best-effort: it runs in its own
transaction(s) after the STOP has already committed, and never propagates an error back to
the stop path — an unscored run is recoverable (the score endpoint recomputes on demand),
a rolled-back stop is not.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aegis_agents.runtime.factory import create_task_executor
from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import AegisSettings
from aegis_contracts.reports import TriggerScribeRequestV1
from aegis_contracts.versioning import TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_scoring.service import ScoringService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_api.runs.service import WORKSPACE_ROOT

logger = logging.getLogger(__name__)

_scoring_service = ScoringService()


async def finalize_stopped_run(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    settings: AegisSettings | None = None,
    scenarios_root: Path | None = None,
) -> None:
    """Score a stopped run and, when possible, generate its after-action report.

    Idempotent and best-effort: scoring dedups on its provenance fingerprint, the SCRIBE
    trigger dedups on a per-run idempotency key, and every failure is logged and swallowed
    so a second call (e.g. manual stop after the ticker already finalized) is harmless.
    """
    root = scenarios_root or (WORKSPACE_ROOT / "scenarios")

    # Score is the primary deliverable: it tolerates a run with zero incidents (the facts
    # assembler resolves incident_id=None gracefully), so it is produced for every stop.
    try:
        async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
            await _scoring_service.score_run(uow, run_id=run_id, scenarios_root=root)
    except Exception:  # noqa: BLE001 — finalization must never fail the stop path
        logger.warning("Auto-scoring failed for stopped run %s", run_id, exc_info=True)

    # After-action report is best-effort: SCRIBE requires an incident with WATCHTOWER /
    # ORACLE / BASTION artifacts, which an unattended run may never accumulate. Missing
    # prerequisites raise inside the coordinator and are treated as "nothing to report".
    try:
        await _generate_after_action_report(session_maker, run_id=run_id, settings=settings)
    except Exception:  # noqa: BLE001
        logger.info(
            "Auto after-action report skipped for stopped run %s (no complete investigation)",
            run_id,
            exc_info=True,
        )


async def _generate_after_action_report(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    settings: AegisSettings | None,
) -> None:
    # Imported lazily: the SCRIBE coordinator pulls in the full agent runtime, which is
    # heavier than the scoring path and only needed when an investigation exists.
    from aegis_agents.roles.scribe.coordinator import ScribeCoordinator

    request = TriggerScribeRequestV1(
        schema_version=TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
        run_id=run_id,
        incident_id=None,
        trace_id=new_runtime_id("trc"),
        idempotency_key=f"auto-scribe-{run_id}",
    )
    coordinator = ScribeCoordinator()
    executor = create_task_executor()
    async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
        result = await coordinator.trigger_for_run(uow, request)
        task = await uow.agent_tasks.get_by_id(result.scribe_task_id)
        if task is not None and task.status.value == "queued":
            await executor.execute(uow, task_id=task.id)
