"""Unit tests for the in-process simulation tick engine.

Fully offline: the tick engine's dependencies (command service, unit of work, run listing,
detection) are injected as fakes so the stepping / horizon / detection-cursor logic is
exercised without a database or event loop scheduler.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from aegis_api.runs.tick_engine import SimulationTicker
from aegis_contracts import RunCreateRequestV1, SimulationCommandType
from aegis_simulation.run_command_service import draw_random_seed

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _settings(**overrides: object) -> SimpleNamespace:
    base = {
        "AEGIS_SIM_TICK_ENABLED": True,
        "AEGIS_SIM_TICK_INTERVAL_SECONDS": 0.01,
        "AEGIS_SIM_STEPS_PER_TICK": 1,
        "AEGIS_SIM_MAX_SIM_SECONDS": 25,
        # High enough that isolation/eviction tests never trip the quarantine path; the
        # breaker has its own dedicated tests.
        "AEGIS_SIM_TICK_FAILURE_THRESHOLD": 1_000,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeRuntime:
    def __init__(self, initial: datetime, *, queue_empty: bool = False) -> None:
        self.configuration = SimpleNamespace(initial_sim_time=initial)
        self.clock = SimpleNamespace(sim_time=initial)
        # peek() returns None only for an exhausted queue; a sentinel otherwise so the
        # horizon (not exhaustion) drives completion in most tests.
        self.queue = SimpleNamespace(peek=lambda: None if queue_empty else object())
        # None while the win/lose race is still on; a resolution snapshot once decided.
        self.run_outcome: object | None = None


class _FakeCommandService:
    """Stands in for RunCommandService: records commands and advances a fake clock."""

    def __init__(self, *, step_delta_seconds: float, fail_runs: set[str] | None = None) -> None:
        self.runtime_cache: dict[str, SimpleNamespace] = {}
        self.statuses: dict[str, str] = {}
        self.step_calls: list[tuple[str, str]] = []
        self.stop_calls: list[tuple[str, str]] = []
        self.evicted: list[str] = []
        self._locks: dict[str, asyncio.Lock] = {}
        self._step_delta = timedelta(seconds=step_delta_seconds)
        self._fail_runs = fail_runs or set()

    def register(self, run_id: str, *, status: str = "running", queue_empty: bool = False) -> None:
        self.statuses[run_id] = status
        self.runtime_cache[run_id] = SimpleNamespace(
            runtime=_FakeRuntime(_T0, queue_empty=queue_empty)
        )

    def lock_for(self, run_id: str) -> asyncio.Lock:
        return self._locks.setdefault(run_id, asyncio.Lock())

    def evict(self, run_id: str) -> None:
        self.evicted.append(run_id)
        self.runtime_cache.pop(run_id, None)

    async def execute_lifecycle_command(
        self, uow: object, run_id: str, command_type: SimulationCommandType, *, idempotency_key: str
    ) -> SimpleNamespace:
        if command_type is SimulationCommandType.STEP:
            if run_id in self._fail_runs:
                raise RuntimeError("boom")
            self.step_calls.append((run_id, idempotency_key))
            self.runtime_cache[run_id].runtime.clock.sim_time += self._step_delta
        elif command_type is SimulationCommandType.STOP:
            self.stop_calls.append((run_id, idempotency_key))
            self.statuses[run_id] = "stopped"
        return SimpleNamespace(events_emitted=1)


class _FakeUow:
    def __init__(
        self, svc: _FakeCommandService, high_water: list[int], events: list[object]
    ) -> None:
        self._svc = svc
        self._high_water = high_water
        self._events = events

    async def __aenter__(self) -> _FakeUow:
        svc = self._svc
        high_water = self._high_water
        events = self._events

        class _Runs:
            async def get_by_id(self, run_id: str) -> SimpleNamespace | None:
                status = svc.statuses.get(run_id)
                if status is None:
                    return None
                return SimpleNamespace(id=run_id, status=status)

            async def list_running(self) -> list[SimpleNamespace]:
                return [
                    SimpleNamespace(id=rid)
                    for rid, st in svc.statuses.items()
                    if st == "running"
                ]

        class _Events:
            async def next_sequence(self, run_id: str) -> int:
                return high_water[0] + 1

            async def list_by_run(self, run_id: str, *, limit: int = 10_000) -> list[object]:
                return list(events)

        self.runs = _Runs()
        self.events = _Events()
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _ticker(
    svc: _FakeCommandService,
    settings: SimpleNamespace,
    *,
    high_water: list[int] | None = None,
    events: list[object] | None = None,
) -> SimulationTicker:
    hw = high_water if high_water is not None else [0]
    evs = events if events is not None else []
    return SimulationTicker(
        command_service=svc,  # type: ignore[arg-type]
        session_maker=lambda: None,  # type: ignore[arg-type]
        settings=settings,  # type: ignore[arg-type]
        uow_factory=lambda: _FakeUow(svc, hw, evs),  # type: ignore[arg-type]
        run_lister=lambda: _list_running(svc),
    )


async def _list_running(svc: _FakeCommandService) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=rid) for rid, st in svc.statuses.items() if st == "running"]


@pytest.mark.asyncio
async def test_advance_steps_running_run_until_horizon_then_stops() -> None:
    svc = _FakeCommandService(step_delta_seconds=10)
    svc.register("run:1")
    ticker = _ticker(svc, _settings(AEGIS_SIM_MAX_SIM_SECONDS=25))

    # Each cycle steps once (10s of sim time). Horizon is 25s: reached after the 3rd step.
    assert await ticker._advance_run("run:1") is False
    assert await ticker._advance_run("run:1") is False
    assert await ticker._advance_run("run:1") is True

    assert len(svc.step_calls) == 3
    assert len(svc.stop_calls) == 1
    assert svc.statuses["run:1"] == "stopped"
    # Idempotency keys are unique per step so no false DUPLICATE_COMMAND dedup.
    assert len({key for _, key in svc.step_calls}) == 3


@pytest.mark.asyncio
async def test_resolved_outcome_completes_run_before_horizon() -> None:
    """A decided run must stop, not keep stepping to the horizon.

    ``sim.run.outcome_resolved`` means the race is over. Leaving the run RUNNING for the
    remaining ~19 sim-minutes is what made the live header, after-action (409), reports
    (empty) and replay all disagree about whether the run had ended.
    """
    svc = _FakeCommandService(step_delta_seconds=1)
    svc.register("run:1")
    ticker = _ticker(svc, _settings(AEGIS_SIM_MAX_SIM_SECONDS=100_000))

    assert await ticker._advance_run("run:1") is False
    svc.runtime_cache["run:1"].runtime.run_outcome = SimpleNamespace(outcome="win")

    assert await ticker._advance_run("run:1") is True
    assert len(svc.stop_calls) == 1
    assert svc.statuses["run:1"] == "stopped"


@pytest.mark.asyncio
async def test_exhausted_queue_completes_run_before_horizon() -> None:
    # Small step delta so the horizon is far off; the empty queue is what completes the run.
    svc = _FakeCommandService(step_delta_seconds=1)
    svc.register("run:1", queue_empty=True)
    ticker = _ticker(svc, _settings(AEGIS_SIM_MAX_SIM_SECONDS=100_000))

    assert await ticker._advance_run("run:1") is True
    assert len(svc.step_calls) == 1
    assert len(svc.stop_calls) == 1
    assert svc.statuses["run:1"] == "stopped"


@pytest.mark.asyncio
async def test_paused_run_is_not_stepped() -> None:
    svc = _FakeCommandService(step_delta_seconds=10)
    svc.register("run:1", status="paused")
    ticker = _ticker(svc, _settings())

    assert await ticker._advance_run("run:1") is False
    assert svc.step_calls == []
    assert svc.stop_calls == []


@pytest.mark.asyncio
async def test_steps_per_tick_advances_multiple_steps() -> None:
    svc = _FakeCommandService(step_delta_seconds=1)
    svc.register("run:1")
    ticker = _ticker(svc, _settings(AEGIS_SIM_STEPS_PER_TICK=4, AEGIS_SIM_MAX_SIM_SECONDS=10_000))

    completed = await ticker._advance_run("run:1")
    assert completed is False
    assert len(svc.step_calls) == 4


@pytest.mark.asyncio
async def test_per_run_failure_isolated_and_evicts() -> None:
    svc = _FakeCommandService(step_delta_seconds=1, fail_runs={"run:bad"})
    svc.register("run:bad")
    svc.register("run:ok")
    ticker = _ticker(svc, _settings(AEGIS_SIM_MAX_SIM_SECONDS=10_000))
    # Skip detection/finalize side effects — this test isolates the stepping loop.
    async def _noop_detection(run_id: str) -> None:
        return None

    ticker._run_detection = _noop_detection  # type: ignore[assignment]

    await ticker._tick_once()

    assert "run:bad" in svc.evicted
    assert any(rid == "run:ok" for rid, _ in svc.step_calls)
    assert all(rid != "run:bad" for rid, _ in svc.step_calls)


@pytest.mark.asyncio
async def test_quarantined_run_finalizes_its_agent_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run the engine cannot advance is forced terminal AND its in-flight agent
    tasks are cancelled — the quarantine path must not leave copilot cards spinning
    on a dead run (the one stop path that bypasses lifecycle.finalize_stopped_run)."""
    svc = _FakeCommandService(step_delta_seconds=1, fail_runs={"run:bad"})
    svc.register("run:bad")
    ticker = _ticker(svc, _settings(AEGIS_SIM_TICK_FAILURE_THRESHOLD=1))
    finalized: list[str] = []

    async def _spy_finalize(uow: object, *, run_id: str) -> int:
        finalized.append(run_id)
        return 0

    monkeypatch.setattr(
        "aegis_api.runs.tick_engine.finalize_tasks_for_stopped_run", _spy_finalize
    )

    await ticker._tick_once()

    assert svc.statuses["run:bad"] == "stopped"
    assert finalized == ["run:bad"]


def test_reached_horizon_boundary() -> None:
    svc = _FakeCommandService(step_delta_seconds=0)
    ticker = _ticker(svc, _settings(AEGIS_SIM_MAX_SIM_SECONDS=25))

    below = _FakeRuntime(_T0)
    below.clock.sim_time = _T0 + timedelta(seconds=24)
    assert ticker._reached_horizon(below) is False  # type: ignore[arg-type]

    at = _FakeRuntime(_T0)
    at.clock.sim_time = _T0 + timedelta(seconds=25)
    assert ticker._reached_horizon(at) is True  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_detection_runs_only_when_new_events_arrive(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _FakeCommandService(step_delta_seconds=1)
    svc.register("run:1")
    high_water = [5]
    events = [SimpleNamespace(sequence=1)]
    ticker = _ticker(svc, _settings(), high_water=high_water, events=events)

    calls: list[str] = []

    async def _fake_detection(
        uow: object,
        *,
        run_id: str,
        events: list[object],
        baselines: object,
        dry_run: bool,
    ) -> object:
        calls.append(run_id)
        return SimpleNamespace()

    monkeypatch.setattr("aegis_api.runs.tick_engine.run_detection_for_events", _fake_detection)

    # Cold cursor -> evaluate; high-water unchanged -> skip; high-water advances -> evaluate.
    await ticker._run_detection("run:1")
    await ticker._run_detection("run:1")
    high_water[0] = 8
    await ticker._run_detection("run:1")

    assert calls == ["run:1", "run:1"]


def test_run_create_request_seed_is_optional() -> None:
    without_seed = RunCreateRequestV1(schemaVersion=1, scenarioPackagePath="scenarios/x")
    assert without_seed.seed is None
    with_seed = RunCreateRequestV1(schemaVersion=1, scenarioPackagePath="scenarios/x", seed=42)
    assert with_seed.seed == 42


def test_draw_random_seed_in_signed_32bit_range() -> None:
    for _ in range(2000):
        seed = draw_random_seed()
        assert 1 <= seed <= 2**31 - 1
