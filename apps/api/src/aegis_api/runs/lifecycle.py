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

    # After-action report degrades instead of dead-ending: when the run accumulated a full
    # WATCHTOWER / ORACLE / BASTION investigation the SCRIBE agent narrates it, and when it
    # did not — the common case for an unattended run, or one whose provider was down — a
    # deterministic report is assembled from persisted state instead. The guard stays
    # because finalization must never fail the stop path, but it is now the exception
    # rather than the norm.
    try:
        await _generate_after_action_report(session_maker, run_id=run_id, settings=settings)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Auto after-action report failed for stopped run %s",
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
    # heavier than the scoring path.
    from aegis_agents.roles.scribe.coordinator import ScribeCoordinator, ScribeReportOutcome

    request = TriggerScribeRequestV1(
        schema_version=TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
        run_id=run_id,
        incident_id=None,
        # Stable per run: re-finalizing (manual stop after the ticker already finalized)
        # resolves to the same SCRIBE task instead of queueing a second one.
        trace_id=new_runtime_id("trc"),
        idempotency_key=f"auto-scribe-{run_id}",
    )
    coordinator = ScribeCoordinator()
    async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
        result = await coordinator.ensure_report_for_run(uow, request)
        if result.outcome is not ScribeReportOutcome.AGENT_TASK_QUEUED:
            logger.info(
                "After-action report for run %s finalized as %s",
                run_id,
                result.outcome.value,
            )
            return
        # Only the agent path needs the runtime; building the executor is deferred until
        # here so a deterministic finalization never touches the model provider stack.
        executor = create_task_executor()
        task = (
            await uow.agent_tasks.get_by_id(result.scribe_task_id)
            if result.scribe_task_id is not None
            else None
        )
        if task is not None and task.status.value == "queued":
            try:
                await executor.execute(uow, task_id=task.id)
            except Exception:  # noqa: BLE001 — the safety net below covers the failure
                logger.warning(
                    "SCRIBE task %s failed for stopped run %s; falling back to a "
                    "deterministic after-action report",
                    task.id,
                    run_id,
                    exc_info=True,
                )

    # Safety net, in its own unit of work so a session poisoned by the failed agent task
    # cannot take it down with it: a run whose investigation *was* complete still ends up
    # with no report if the SCRIBE generation itself fails (an unreachable provider, an
    # ungroundable narrative). This is a no-op when the agent path wrote one.
    async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
        fallback = await coordinator.ensure_deterministic_report(uow, request)
        logger.info(
            "After-action report for run %s finalized as %s",
            run_id,
            fallback.outcome.value,
        )
