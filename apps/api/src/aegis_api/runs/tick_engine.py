"""In-process simulation tick engine.

The API process owns the single shared :class:`RunCommandService` runtime cache, which
makes it the natural single writer for advancing runs. This lifespan-managed background
service wakes on a fixed cadence, discovers every RUNNING run from the database, and steps
each one through the same command service the manual lifecycle routes use — serialized by
the same per-run lock so a tick never races a manual command on the same runtime.

Per cycle, for each running run:

* step ``AEGIS_SIM_STEPS_PER_TICK`` times, stopping early if the scenario completion
  horizon (``AEGIS_SIM_MAX_SIM_SECONDS`` of virtual time) is reached;
* run live detection over the run's events when new ones have arrived;
* on horizon completion, STOP the run and produce its after-action artifacts.

Every run is isolated: a failure on one run is logged, its cached runtime evicted (so the
next cycle re-restores clean state), and the remaining runs still advance. Pausing or
stopping a run (manually) is respected because status is re-checked under the lock before
each step and RUNNING runs are re-discovered from the database each cycle (restart-safe).

Eviction only helps when the next attempt can succeed. A run whose state the engine simply
cannot advance would otherwise fail identically on every cycle for as long as the process
lives, so consecutive failures are counted per run and a run that trips
``AEGIS_SIM_TICK_FAILURE_THRESHOLD`` is quarantined: taken to a terminal status, which
removes it from the RUNNING set the ticker rediscovers each cycle, and reported at ERROR.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime

from aegis_contracts import AegisSettings, SimulationCommandType
from aegis_contracts.detection import StatisticalBaselineV1
from aegis_contracts.entities import RunV1
from aegis_contracts.simulation import SimulationRunStatus
from aegis_incidents.pipeline import run_detection_for_events
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain import (
    GovernedAsset,
    ThreatTempoState,
    TriggeredCondition,
    build_governing_map,
    compute_threat_tempo,
)
from aegis_simulation_domain.runtime import SimulationRuntime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_api.runs.lifecycle import finalize_stopped_run

logger = logging.getLogger(__name__)

_RUNNING = SimulationRunStatus.RUNNING.value
_STOPPED = SimulationRunStatus.STOPPED.value
# Full run history is loaded for detection each cycle with new events; the feature engine
# aggregates events into sim-time windows, so a partial (sequence-windowed) slice would
# split windows and corrupt feature vectors. Re-persistence is idempotent (alert dedup),
# so a full re-scan is correct; this cap simply bounds a single query.
_DETECTION_EVENT_LIMIT = 1_000_000

UowFactory = Callable[[], PostgresUnitOfWork]
RunLister = Callable[[], Awaitable[list[RunV1]]]


class SimulationTicker:
    def __init__(
        self,
        *,
        command_service: RunCommandService,
        session_maker: async_sessionmaker[AsyncSession],
        settings: AegisSettings,
        uow_factory: UowFactory | None = None,
        run_lister: RunLister | None = None,
    ) -> None:
        self._command_service = command_service
        self._session_maker = session_maker
        self._settings = settings
        self._uow_factory: UowFactory = uow_factory or (
            lambda: PostgresUnitOfWork(session_maker, settings=settings)
        )
        self._run_lister: RunLister = run_lister or self._list_running_runs
        # Restart-safe in the sense that matters: an empty cursor after a restart triggers a
        # one-time full re-scan whose alert persistence is idempotent, so no alert is lost or
        # duplicated. Steady-state, it skips detection for ticks that added no new events.
        self._detection_cursors: dict[str, int] = {}
        self._baselines_loaded = False
        self._baselines: StatisticalBaselineV1 | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        # Fog-of-war threat-tempo caches (per run). The governing map is manifest-static;
        # ``first_triggered_at`` stamps the sim-time we first observed each hidden condition
        # triggered (elapsed-since-trigger proxy that ramps deterministically with the tick
        # cadence); ``alerted`` is refreshed whenever detection runs.
        self._tempo_governing: dict[str, dict[str, GovernedAsset]] = {}
        self._tempo_first_triggered_at: dict[str, dict[str, datetime]] = {}
        # Circuit breaker: consecutive failed ticks per run, cleared by any successful
        # advance. Only lives for the process — a restart gets a fresh budget, which is the
        # behaviour we want, since a restart is also the most likely thing to have fixed it.
        self._consecutive_failures: dict[str, int] = {}

    async def start(self) -> None:
        if not self._settings.AEGIS_SIM_TICK_ENABLED:
            logger.info("Simulation tick engine disabled (AEGIS_SIM_TICK_ENABLED=false)")
            return
        if self._task is not None:
            return
        self._stopping.clear()
        # A ``restartExisting`` relaunch destroys a run and recreates it under the same
        # derived id, so every cache below keyed by that id has to be dropped with it.
        self._command_service.add_run_reset_listener(self._forget_run_state)
        self._task = asyncio.create_task(self._run_loop(), name="aegis-sim-ticker")
        logger.info(
            "Simulation tick engine started (interval=%ss, steps/tick=%s, horizon=%ss)",
            self._settings.AEGIS_SIM_TICK_INTERVAL_SECONDS,
            self._settings.AEGIS_SIM_STEPS_PER_TICK,
            self._settings.AEGIS_SIM_MAX_SIM_SECONDS,
        )

    async def stop(self) -> None:
        self._stopping.set()
        # The command service is a process-wide singleton that outlives this ticker (tests
        # build several apps against it), so a stopped ticker must not stay subscribed.
        self._command_service.remove_run_reset_listener(self._forget_run_state)
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
            logger.info("Simulation tick engine stopped")

    async def _run_loop(self) -> None:
        interval = self._settings.AEGIS_SIM_TICK_INTERVAL_SECONDS
        while not self._stopping.is_set():
            try:
                await self._tick_once()
            except Exception:  # noqa: BLE001 — the loop must survive any single cycle failure
                logger.exception("Simulation tick cycle failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=interval)

    async def _tick_once(self) -> None:
        runs = await self._run_lister()
        for run in runs:
            if self._stopping.is_set():
                break
            try:
                completed = await self._advance_run(run.id)
            except Exception:  # noqa: BLE001 — isolate per-run failures
                await self._record_tick_failure(run.id)
                continue
            self._consecutive_failures.pop(run.id, None)
            try:
                await self._run_detection(run.id)
            except Exception:  # noqa: BLE001 — detection must never kill the ticker
                logger.warning("Live detection failed for run %s", run.id, exc_info=True)
            try:
                await self._update_threat_tempo(run.id)
            except Exception:  # noqa: BLE001 — tempo is ambient UX, never fatal
                logger.debug("Threat tempo update failed for run %s", run.id, exc_info=True)
            if completed:
                self._reset_tempo_state(run.id)
                await finalize_stopped_run(
                    self._session_maker,
                    run_id=run.id,
                    settings=self._settings,
                )

    async def _record_tick_failure(self, run_id: str) -> None:
        """Log and evict after a failed tick, quarantining the run once it stops recovering."""
        failures = self._consecutive_failures.get(run_id, 0) + 1
        self._consecutive_failures[run_id] = failures
        logger.warning(
            "Tick failed for run %s (%d consecutive); evicting cached runtime",
            run_id,
            failures,
        )
        logger.debug("Tick failure detail for run %s", run_id, exc_info=True)
        self._command_service.evict(run_id)
        if failures < self._settings.AEGIS_SIM_TICK_FAILURE_THRESHOLD:
            return
        logger.error(
            "Run %s failed %d consecutive ticks; quarantining it so the shared tick loop "
            "stops retrying a run it cannot advance",
            run_id,
            failures,
        )
        try:
            await self._quarantine_run(run_id)
        except Exception:  # noqa: BLE001 — quarantine must never kill the tick loop
            # Leave the counter standing so the very next failure retries the quarantine
            # rather than waiting out another full threshold.
            logger.exception("Failed to quarantine run %s", run_id)
            return
        self._consecutive_failures.pop(run_id, None)

    async def _quarantine_run(self, run_id: str) -> None:
        """Take a run the engine cannot advance to a terminal status.

        Tries the real lifecycle STOP first, so a quarantined run ends up indistinguishable
        from a manually stopped one (``sim.run.stopped`` emitted, faithful final checkpoint).
        That path needs a working runtime, which is precisely what is in doubt here, so a
        failure falls back to writing the terminal status straight onto the run row — status
        is what ``list_running`` filters on, so that is what actually ends the retry loop.
        """
        async with self._command_service.lock_for(run_id):
            try:
                async with self._uow_factory() as uow:
                    await self._command_service.execute_lifecycle_command(
                        uow,
                        run_id,
                        SimulationCommandType.STOP,
                        idempotency_key=self._stop_key(run_id),
                    )
            except Exception:  # noqa: BLE001 — fall back to the durable status write
                logger.warning(
                    "Lifecycle STOP unavailable for quarantined run %s; forcing terminal "
                    "status directly",
                    run_id,
                    exc_info=True,
                )
                self._command_service.evict(run_id)
                async with self._uow_factory() as uow:
                    await self._force_stopped_status(uow, run_id)
        self._reset_tempo_state(run_id)
        self._detection_cursors.pop(run_id, None)

    @staticmethod
    async def _force_stopped_status(uow: PostgresUnitOfWork, run_id: str) -> None:
        run = await uow.runs.get_by_id(run_id)
        if run is None or run.status == _STOPPED:
            return
        await uow.runs.update_with_revision(
            run.model_copy(update={"status": _STOPPED, "revision": run.revision + 1}),
            expected_revision=run.revision,
        )

    async def _advance_run(self, run_id: str) -> bool:
        """Step a run up to the horizon. Returns True if the ticker STOPped it (completion).

        Holds the per-run lock across every step (and the completion STOP) so no manual
        command or other tick interleaves on the shared cached runtime. Each step is its own
        transaction: multiple run-row updates in one session would collide on the optimistic
        revision guard.
        """
        horizon_reached = False
        async with self._command_service.lock_for(run_id):
            for _ in range(self._settings.AEGIS_SIM_STEPS_PER_TICK):
                async with self._uow_factory() as uow:
                    run = await uow.runs.get_by_id(run_id)
                    if run is None or run.status != _RUNNING:
                        # Paused or stopped between discovery and now — respect it.
                        return False
                    await self._command_service.execute_lifecycle_command(
                        uow,
                        run_id,
                        SimulationCommandType.STEP,
                        idempotency_key=self._step_key(run_id),
                    )
                entry = self._command_service.runtime_cache.get(run_id)
                if entry is not None and self._is_complete(entry.runtime):
                    horizon_reached = True
                    break
            if horizon_reached:
                async with self._uow_factory() as uow:
                    await self._command_service.execute_lifecycle_command(
                        uow,
                        run_id,
                        SimulationCommandType.STOP,
                        idempotency_key=self._stop_key(run_id),
                    )
        return horizon_reached

    def _is_complete(self, runtime: SimulationRuntime) -> bool:
        """A run completes at the sim-time horizon or when its event queue is exhausted.

        Silent Relay's baseline generators reschedule forever, so the sim-time horizon is
        the effective completion signal there; the queue-exhaustion check makes the ticker
        correct for finite scenarios (e.g. the deterministic tutorial) that simply run out
        of scheduled work before the horizon.
        """
        return self._reached_horizon(runtime) or runtime.queue.peek() is None

    def _reached_horizon(self, runtime: SimulationRuntime) -> bool:
        elapsed = (
            runtime.clock.sim_time - runtime.configuration.initial_sim_time
        ).total_seconds()
        return elapsed >= self._settings.AEGIS_SIM_MAX_SIM_SECONDS

    async def _run_detection(self, run_id: str) -> None:
        async with self._uow_factory() as uow:
            high_water = (await uow.events.next_sequence(run_id)) - 1
            cursor = self._detection_cursors.get(run_id)
            if cursor is not None and high_water <= cursor:
                return  # No new events since the last evaluation.
            events = await uow.events.list_by_run(run_id, limit=_DETECTION_EVENT_LIMIT)
            if not events:
                return
            await run_detection_for_events(
                uow,
                run_id=run_id,
                events=events,
                baselines=self._load_baselines(),
                dry_run=False,
            )
            # Advance past any alert events detection just appended so the next cycle only
            # re-evaluates when the simulation itself produced new events.
            new_high = (await uow.events.next_sequence(run_id)) - 1
        self._detection_cursors[run_id] = new_high

    async def _update_threat_tempo(self, run_id: str) -> None:
        """Recompute the ambient threat-tempo scalar from the cached runtime.

        Reads the run's live hidden-condition state (triggered/revealed) in memory and, only
        when undisclosed triggered conditions actually exist, does one cheap alert lookup to
        see whether detection has since disclosed them. Never touches the authoritative event
        stream, so it cannot perturb determinism. Scalar only — the stored value carries no
        asset or condition identity.
        """
        entry = self._command_service.runtime_cache.get(run_id)
        if entry is None:
            return
        runtime = entry.runtime
        manifest = runtime.manifest
        total = len(manifest.hidden_conditions)
        if total == 0:
            return
        governing = self._tempo_governing.get(run_id)
        if governing is None:
            governing = build_governing_map(manifest)
            self._tempo_governing[run_id] = governing

        current_sim_time = runtime.clock.sim_time
        first_seen = self._tempo_first_triggered_at.setdefault(run_id, {})
        revealed: set[str] = set()
        triggered: list[TriggeredCondition] = []
        for condition_id, state in runtime.world.hidden_conditions.items():
            if state.revealed:
                revealed.add(condition_id)
            if state.triggered:
                triggered_at = first_seen.setdefault(condition_id, current_sim_time)
                triggered.append(TriggeredCondition(condition_id, triggered_at))

        # Only spend a query when there is undisclosed-by-reveal pressure to relieve.
        undisclosed_triggered = [
            condition for condition in triggered if condition.condition_id not in revealed
        ]
        alerted: frozenset[str] = frozenset()
        if undisclosed_triggered:
            alerted = await self._alerted_asset_ids(run_id)

        disclosed_conditions: set[str] = set(revealed)
        for asset_id, governed in governing.items():
            if asset_id in alerted:
                disclosed_conditions |= governed.condition_ids

        tempo = compute_threat_tempo(
            ThreatTempoState(
                current_sim_time=current_sim_time,
                triggered=triggered,
                revealed_condition_ids=frozenset(revealed),
                disclosed_condition_ids=frozenset(disclosed_conditions),
                total_conditions=total,
            ),
            saturation_sim_seconds=self._settings.AEGIS_THREAT_TEMPO_SATURATION_SIM_SECONDS,
        )
        self._command_service.set_threat_tempo(run_id, tempo)

    async def _alerted_asset_ids(self, run_id: str) -> frozenset[str]:
        async with self._uow_factory() as uow:
            alerts = await uow.alerts.list_by_run(run_id)
        return frozenset(alert.asset_id for alert in alerts if alert.asset_id)

    def _forget_run_state(self, run_id: str) -> None:
        """Drop every per-run in-process cache when that run is reset and recreated.

        The fresh run reuses the destroyed run's id and restarts its sequence stream at 0.
        A surviving detection cursor (the old run's high-water sequence) would therefore
        suppress detection until the new run overtook it — no alerts, no incidents, a dead
        tutorial. Threat-tempo first-seen stamps carry the old run's sim-time and would skew
        the tempo scalar; the failure counter would carry a doomed run's strikes onto a
        healthy one. All three are cheap to rebuild: an absent cursor simply triggers one
        idempotent full re-scan.

        Called synchronously by :class:`RunCommandService` while it holds the run's lock, so
        it cannot race a tick on the same run.
        """
        self._detection_cursors.pop(run_id, None)
        self._consecutive_failures.pop(run_id, None)
        self._reset_tempo_state(run_id)

    def _reset_tempo_state(self, run_id: str) -> None:
        self._command_service.clear_threat_tempo(run_id)
        self._tempo_governing.pop(run_id, None)
        self._tempo_first_triggered_at.pop(run_id, None)

    def _load_baselines(self) -> StatisticalBaselineV1 | None:
        if not self._baselines_loaded:
            from aegis_ml.baselines.store import DEFAULT_BASELINE_DIR, load_baseline

            baseline_path = DEFAULT_BASELINE_DIR / "baseline.json"
            self._baselines = load_baseline() if baseline_path.exists() else None
            self._baselines_loaded = True
        return self._baselines

    async def _list_running_runs(self) -> list[RunV1]:
        async with self._uow_factory() as uow:
            return await uow.runs.list_running()

    @staticmethod
    def _step_key(run_id: str) -> str:
        # A unique, always-progressing idempotency key per step. It never appears in event
        # content (only START/STOP/EXECUTE emit a command id into a payload), so a random
        # token cannot affect the determinism-golden normalized hash; keying on a persisted
        # counter instead would risk a post-restart replay storm.
        return f"tick-step-{run_id}-{secrets.token_hex(8)}"

    @staticmethod
    def _stop_key(run_id: str) -> str:
        return f"tick-stop-{run_id}-{secrets.token_hex(8)}"
