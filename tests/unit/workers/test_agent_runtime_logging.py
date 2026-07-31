"""The agent-runtime worker must be observable.

Live evidence from 2026-07-30: ``docker logs aegis-agent-worker-1`` emitted zero
lines across a whole QA session in which every agent task failed. The container
was healthy and polling — it simply had no logger and swallowed every executor
exception with a bare ``continue``, so a total provider outage was
indistinguishable from an idle queue.

Offline: the unit of work and the executor are faked, so no PostgreSQL is needed.
"""

from __future__ import annotations

import asyncio
import logging

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
        return []


class _FakeUoW:
    def __init__(self, tasks: list[_FakeTask]) -> None:
        self._tasks = tasks

    async def __aenter__(self) -> _FakeUoW:
        self.agent_tasks = _FakeAgentTasks(self._tasks)
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def rollback(self) -> None:
        return None


@pytest.mark.asyncio
async def test_task_failure_is_logged_with_the_task_id(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failing task must leave a trace in the worker log, not vanish."""
    monkeypatch.setattr(
        agent_runtime_runner,
        "PostgresUnitOfWork",
        lambda _session_maker: _FakeUoW([_FakeTask("atk_boom")]),
    )

    class _FailingExecutor:
        async def execute(self, _uow: object, _task_id: str) -> None:
            raise RuntimeError("provider unreachable")

    with caplog.at_level(logging.WARNING, logger=agent_runtime_runner.__name__):
        processed = await agent_runtime_runner._poll_once(
            session_maker=None,
            executor=_FailingExecutor(),  # type: ignore[arg-type]
            orphan_lease_seconds=999.0,
            stop_event=asyncio.Event(),
        )

    assert processed == 0
    assert any(
        "atk_boom" in record.getMessage() or record.__dict__.get("taskId") == "atk_boom"
        for record in caplog.records
    ), f"task failure was not logged: {[r.getMessage() for r in caplog.records]}"


@pytest.mark.asyncio
async def test_successful_task_is_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Successful execution is logged too, so an idle worker is distinguishable."""
    monkeypatch.setattr(
        agent_runtime_runner,
        "PostgresUnitOfWork",
        lambda _session_maker: _FakeUoW([_FakeTask("atk_ok")]),
    )

    class _Executor:
        async def execute(self, _uow: object, _task_id: str) -> None:
            return None

    with caplog.at_level(logging.INFO, logger=agent_runtime_runner.__name__):
        processed = await agent_runtime_runner._poll_once(
            session_maker=None,
            executor=_Executor(),  # type: ignore[arg-type]
            orphan_lease_seconds=999.0,
            stop_event=asyncio.Event(),
        )

    assert processed == 1
    assert caplog.records, "a completed task produced no log line"


@pytest.mark.asyncio
async def test_an_idle_poll_stays_quiet(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The loop polls once a second; an empty queue must not flood the log."""
    monkeypatch.setattr(
        agent_runtime_runner,
        "PostgresUnitOfWork",
        lambda _session_maker: _FakeUoW([]),
    )

    class _Executor:
        async def execute(self, _uow: object, _task_id: str) -> None:  # pragma: no cover
            raise AssertionError("nothing queued")

    with caplog.at_level(logging.INFO, logger=agent_runtime_runner.__name__):
        await agent_runtime_runner._poll_once(
            session_maker=None,
            executor=_Executor(),  # type: ignore[arg-type]
            orphan_lease_seconds=999.0,
            stop_event=asyncio.Event(),
        )

    assert not caplog.records


def test_worker_configures_root_logging_at_startup() -> None:
    """Without this the handlers never exist and every log line is discarded."""
    source = agent_runtime_runner.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "init_observability" in text, (
        "the agent-runtime worker never configures logging, so nothing it logs "
        "can reach the container's stdout"
    )
