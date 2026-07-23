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
from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import AegisSettings, AlertV1, RulesOfEngagementV1, RunV1, StandingDirectiveV1
from aegis_contracts.simulation import SimulationRunStatus
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_api.directives.events import build_directive_triggered_event

logger = logging.getLogger(__name__)

_RUNNING = SimulationRunStatus.RUNNING.value


def _directive_matches(
    directive: StandingDirectiveV1, asset_id: str, zone_id: str | None
) -> bool:
    """A directive matches an alert when it is unscoped, or the alert's asset (or the
    asset's zone/cluster) intersects the directive's scope."""
    if not directive.scope_asset_ids and not directive.scope_zone_ids:
        return True
    if asset_id in directive.scope_asset_ids:
        return True
    return zone_id is not None and zone_id in directive.scope_zone_ids


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
            new_alerts = [alert for alert in alerts if alert.id not in seen]
            if not new_alerts:
                return

            bias_guard_on = run.loadout.bias_guard if run.loadout is not None else True
            directives = await uow.directives.list_active_for_run(run_id)
            # Lazily materialised once per cycle: asset->zone map (only when a directive
            # scopes by zone) and the hypothesis-asset set (only when bias guard is on).
            cluster_map: dict[str, str] | None = None
            hypothesis_assets: set[str] | None = None

            for alert in new_alerts:
                seen.add(alert.id)
                await self._service.on_new_alert(
                    uow,
                    run_id=run_id,
                    alert_id=alert.id,
                    asset_id=alert.asset_id,
                    alert_title=alert.title,
                    roe=roe,
                )
                if directives:
                    if cluster_map is None and any(d.scope_zone_ids for d in directives):
                        cluster_map = await self._cluster_map(uow, run_id)
                    await self._match_directives(
                        uow, run_id=run_id, alert=alert, directives=directives,
                        cluster_map=cluster_map or {},
                    )
                if bias_guard_on:
                    if hypothesis_assets is None:
                        hypothesis_assets = await self._hypothesis_assets(uow, run_id)
                    if alert.asset_id in hypothesis_assets:
                        await self._service.on_bias_guard(
                            uow,
                            run_id=run_id,
                            alert_id=alert.id,
                            asset_id=alert.asset_id,
                            alert_title=alert.title,
                        )

    async def _match_directives(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        alert: AlertV1,
        directives: list[StandingDirectiveV1],
        cluster_map: dict[str, str],
    ) -> None:
        zone = cluster_map.get(alert.asset_id)
        for directive in directives:
            if not _directive_matches(directive, alert.asset_id, zone):
                continue
            task_id = await self._service.on_directive_match(
                uow,
                run_id=run_id,
                directive_id=directive.id,
                directive_text=directive.text,
                alert_id=alert.id,
                asset_id=alert.asset_id,
                alert_title=alert.title,
            )
            if task_id is None:  # budget denied — nothing was enqueued, so do not signal.
                continue
            next_sequence = await uow.events.next_sequence(run_id)
            await uow.append_event(
                build_directive_triggered_event(
                    event_id=new_runtime_id("evt"),
                    run_id=run_id,
                    sequence=next_sequence,
                    trace_id=new_runtime_id("trc"),
                    directive_id=directive.id,
                    alert_id=alert.id,
                    asset_id=alert.asset_id,
                    task_id=task_id,
                )
            )

    async def _cluster_map(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> dict[str, str]:
        snapshot = await PostgresGraphSnapshotRepository(uow.session).get_latest_for_run(
            run_id
        )
        if snapshot is None:
            return {}
        return {n.id: n.cluster_id for n in snapshot.nodes if n.cluster_id is not None}

    async def _hypothesis_assets(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> set[str]:
        incidents = await uow.incidents.list_by_run(run_id)
        evidence_ids: set[str] = set()
        for incident in incidents:
            hypotheses = await uow.oracle_hypotheses.list_hypotheses_for_incident(
                incident.id
            )
            for hypothesis in hypotheses:
                evidence_ids.update(hypothesis.evidence_ids)
        if not evidence_ids:
            return set()
        evidence = await uow.evidence.get_by_ids(list(evidence_ids))
        return {item.asset_id for item in evidence if item.asset_id is not None}
