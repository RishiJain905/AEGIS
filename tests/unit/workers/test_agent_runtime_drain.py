"""Regression tests for AEGIS-BUG-006 — graceful agent runtime worker shutdown.

The worker must drain the in-flight ``executor.execute`` on SIGTERM/SIGINT
instead of aborting it mid-transaction, and it must not start new tasks once a
stop has been requested. These are offline tests: the DB unit of work and the
executor are faked, so no PostgreSQL is required.
"""

from __future__ import annotations

import asyncio

import pytest
from aegis_workers import agent_runtime_runner


class _FakeTask:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


class _FakeAgentTasks:
    def __init__(self, tasks: list[_FakeTask]) -> None:
        self._tasks = tasks

    async def list_queued(self, *, limit: int = 10) -> list[_FakeTask]:
        return list(self._tasks)

    async def list_running(self) -> list[_FakeTask]:
        # Orphan reclaim runs first each poll; no orphans in this drain test.
        return []


class _FakeUoW:
    def __init__(self, tasks: list[_FakeTask]) -> None:
        self._tasks = tasks

    async def __aenter__(self) -> _FakeUoW:
        self.agent_tasks = _FakeAgentTasks(self._tasks)
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_poll_once_finishes_inflight_then_skips_new_after_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = [_FakeTask("t1"), _FakeTask("t2")]
    monkeypatch.setattr(
        agent_runtime_runner,
        "PostgresUnitOfWork",
        lambda _session_maker: _FakeUoW(tasks),
    )

    stop = asyncio.Event()
    executed: list[str] = []

    class _FakeExecutor:
        async def execute(self, _uow: object, task_id: str) -> None:
            executed.append(task_id)
            if task_id == "t1":
                # Shutdown requested while the first task is in flight.
                stop.set()
            await asyncio.sleep(0)

    processed = await agent_runtime_runner._poll_once(
        session_maker=None,
        executor=_FakeExecutor(),  # type: ignore[arg-type]
        orphan_lease_seconds=999.0,
        stop_event=stop,
    )

    # t1 ran to completion; t2 was never started because stop was set.
    assert executed == ["t1"]
    assert processed == 1


@pytest.mark.asyncio
async def test_run_poll_loop_exits_after_inflight_poll_completes() -> None:
    stop = asyncio.Event()
    poll_started = asyncio.Event()
    completed: list[int] = []

    async def poll() -> int:
        poll_started.set()
        await asyncio.sleep(0.02)
        completed.append(1)
        return 0

    loop_task = asyncio.create_task(
        agent_runtime_runner._run_poll_loop(poll, stop, interval=0.01)
    )
    await asyncio.wait_for(poll_started.wait(), timeout=1.0)
    stop.set()

    await asyncio.wait_for(loop_task, timeout=1.0)
    # The in-flight poll drained to completion before the loop exited.
    assert completed == [1]
