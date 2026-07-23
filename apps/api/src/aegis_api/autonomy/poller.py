"""Event-driven autonomous triage poller.

The autonomy loop must react to NEW alerts without per-tick LLM churn. Live detection runs
inside the tick engine (which this phase may not edit), and cross-service in-process
callbacks would couple incidents -> agents. The clean seam in this architecture is the
persisted alert stream: alerts are written to authoritative rows by the detection pipeline,
so a lightweight lifespan-managed poller consumes newly-persisted alerts by a per-run
in-memory cursor and hands each to :class:`AutonomyTriageService` (enqueue-only, budget- and
RoE-gated). This keeps the loop fully decoupled from the tick engine and the incidents
pipeline, restart-safe (a fresh process re-derives its cursor; budgets bound any re-scan),
and free of any new storage.

Enqueued tasks are QUEUED and executed by the normal agent runtime, so the poller itself
never runs the model — a burst of alerts cannot stall the poll loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aegis_agents.autonomy import AutonomyBudget, AutonomyTriageService
from aegis_contracts import AegisSettings, RulesOfEngagementV1, RunV1
from aegis_contracts.simulation import SimulationRunStatus
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_RUNNING = SimulationRunStatus.RUNNING.value


class AutonomyPoller:
    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
        settings: AegisSettings,
        service: AutonomyTriageService | None = None,
    ) -> None:
        self._session_maker = session_maker
        self._settings = settings
        self._service = service or AutonomyTriageService(
            budget=AutonomyBudget.from_settings(settings)
        )
        # Per-run set of alert ids already handed to the autonomy service this process
        # lifetime, so each alert triggers at most one enqueue attempt.
        self._seen_alerts: dict[str, set[str]] = {}
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not self._settings.AEGIS_AUTONOMY_ENABLED:
            logger.info("Autonomy poller disabled (AEGIS_AUTONOMY_ENABLED=false)")
            return
        if self._task is not None:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_loop(), name="aegis-autonomy-poller")
        logger.info(
            "Autonomy poller started (interval=%ss, budget concurrent=%s cap=%s cooldown=%ss)",
            self._settings.AEGIS_AUTONOMY_POLL_INTERVAL_SECONDS,
            self._settings.AEGIS_AUTONOMY_MAX_CONCURRENT_TASKS,
            self._settings.AEGIS_AUTONOMY_MAX_TASKS_PER_RUN,
            self._settings.AEGIS_AUTONOMY_PER_ASSET_COOLDOWN_SECONDS,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is None:
            return
        try:
            await asyncio.wait_for(self._task, timeout=10.0)
        except TimeoutError:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        finally:
            self._task = None
            logger.info("Autonomy poller stopped")

    async def _run_loop(self) -> None:
        interval = self._settings.AEGIS_AUTONOMY_POLL_INTERVAL_SECONDS
        while not self._stopping.is_set():
            try:
                await self._poll_once()
            except Exception:  # noqa: BLE001 — the loop must survive any single cycle failure
                logger.exception("Autonomy poll cycle failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=interval)

    async def _poll_once(self) -> None:
        async with PostgresUnitOfWork(self._session_maker, settings=self._settings) as uow:
            runs = await uow.runs.list_running()
        for run in runs:
            if self._stopping.is_set():
                break
            try:
                await self._poll_run(run.id, self._roe_for(run))
            except Exception:  # noqa: BLE001 — isolate per-run failures
                logger.warning("Autonomy poll failed for run %s", run.id, exc_info=True)

    @staticmethod
    def _roe_for(run: RunV1) -> RulesOfEngagementV1:
        if run.loadout is not None:
            return run.loadout.roe
        return RulesOfEngagementV1.INVESTIGATE

    async def _poll_run(self, run_id: str, roe: RulesOfEngagementV1) -> None:
        async with PostgresUnitOfWork(self._session_maker, settings=self._settings) as uow:
            run = await uow.runs.get_by_id(run_id)
            if run is None or run.status != _RUNNING:
                return
            alerts = await uow.alerts.list_by_run(run_id)
            seen = self._seen_alerts.setdefault(run_id, set())
            for alert in alerts:
                if alert.id in seen:
                    continue
                seen.add(alert.id)
                await self._service.on_new_alert(
                    uow,
                    run_id=run_id,
                    alert_id=alert.id,
                    asset_id=alert.asset_id,
                    alert_title=alert.title,
                    roe=roe,
                )
