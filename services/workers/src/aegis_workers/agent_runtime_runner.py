"""Poll queued agent tasks and execute them."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from collections.abc import Awaitable, Callable

from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.factory import _resolve_task_timeout_seconds, create_task_executor
from aegis_agents.runtime.recovery import recover_orphaned_tasks, recover_running_tasks
from aegis_contracts import load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


def _orphan_lease_seconds() -> float:
    """Lease TTL after which a RUNNING task is presumed orphaned and reclaimable.

    A task legitimately runs for at most the task timeout (the executor's own
    ``wait_for`` bounds the model call), so anything RUNNING well past that has no
    live executor. Default is 2x the task timeout — comfortably above a real 27B
    turn — so a genuinely in-flight task is never reclaimed. Env-tunable.
    """
    override = os.environ.get("AEGIS_AGENT_ORPHAN_LEASE_SECONDS")
    if override is not None:
        with contextlib.suppress(ValueError):
            value = float(override)
            if value > 0:
                return value
    return 2.0 * _resolve_task_timeout_seconds()


async def _poll_once(
    session_maker: async_sessionmaker[AsyncSession],
    executor: TaskExecutor,
    *,
    orphan_lease_seconds: float,
    stop_event: asyncio.Event | None = None,
) -> int:
    # Reclaim orphans FIRST, every pass, before draining the queue: a task
    # stranded in 'running' by a dead/replaced worker (the split commits the
    # queued->running claim early, so there is no in-band rollback) is returned to
    # 'queued' — attempt incremented, up to the retry cap, then failed — and is
    # picked up by the very same list_queued below. This is the standing safety net
    # for "worker replaced mid-task"; startup recovery only fires once at boot.
    async with PostgresUnitOfWork(session_maker) as uow:
        await recover_orphaned_tasks(uow, older_than_seconds=orphan_lease_seconds)

    processed = 0
    async with PostgresUnitOfWork(session_maker) as uow:
        queued = await uow.agent_tasks.list_queued(limit=10)
    for task in queued:
        # Drain semantics: never start a new task once shutdown has been
        # requested. The task already in flight below is awaited to completion.
        if stop_event is not None and stop_event.is_set():
            break
        # Sweep again between tasks, not just once before the drain. A pass can
        # legitimately execute ten tasks of up to the task timeout each, so a
        # sweep that only ran at the top of the pass could be twenty minutes
        # apart — which is exactly how a stranded task sat in 'running' with a
        # frozen timestamp while this worker visibly processed later ones. The
        # query is one indexed read against a small table; running it per task is
        # cheap, and it is what bounds how long an abandoned turn can spin.
        async with PostgresUnitOfWork(session_maker) as sweep_uow:
            await recover_orphaned_tasks(sweep_uow, older_than_seconds=orphan_lease_seconds)
        async with PostgresUnitOfWork(session_maker) as uow:
            try:
                await executor.execute(uow, task.id)
                processed += 1
                logger.info("Agent task executed", extra={"taskId": task.id})
            except Exception:
                # The executor owns its own commits and persists a terminal task
                # on every failure before re-raising, so nothing here should be
                # pending. Roll back defensively anyway: a bare ``continue`` inside
                # the context manager would otherwise COMMIT any partial, unhandled
                # write (e.g. a claim stranded by an unexpected error), orphaning
                # the task in 'running'.
                #
                # Logging is not optional here: this except used to swallow the
                # failure silently, which is how a total provider outage produced a
                # worker container with zero log lines. The terminal task row in
                # Postgres is the audit record; this line is what makes the failure
                # visible while it is happening.
                logger.warning(
                    "Agent task failed: %s",
                    task.id,
                    extra={"taskId": task.id},
                    exc_info=True,
                )
                await uow.rollback()
                continue
    return processed


async def _run_poll_loop(
    poll: Callable[[], Awaitable[int]],
    stop_event: asyncio.Event,
    *,
    interval: float,
) -> None:
    """Poll until ``stop_event`` is set, sleeping ``interval`` between passes.

    Each ``poll`` call is awaited to completion before the stop is honoured, so
    an in-flight task drains rather than being abandoned mid-transaction.
    """
    while not stop_event.is_set():
        await poll()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval)


async def _run_loop(stop_event: asyncio.Event | None = None) -> None:
    settings = load_settings()
    # Install the root handlers before anything else runs. Without this the
    # process has no logging configuration at all, so every line this module (and
    # the executor beneath it) emits is discarded and the container looks idle
    # even while every task it runs is failing. Mirrors the outbox relay's boot.
    try:
        from aegis_observability.setup import init_observability

        init_observability(
            service_name=getattr(settings, "OTEL_SERVICE_NAME", "aegis-agent-worker"),
            enabled=getattr(settings, "OTEL_ENABLED", True),
            otlp_endpoint=getattr(
                settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
            ),
            otlp_protocol=getattr(settings, "OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"),
            log_level=settings.LOG_LEVEL.value,
            json_logs=getattr(settings, "AEGIS_LOG_JSON", True),
        )
    except Exception:  # noqa: BLE001 — observability must never block the worker
        logging.basicConfig(level=logging.INFO)
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    executor = create_task_executor()
    stop_event = stop_event or asyncio.Event()
    # Startup recovery: any RUNNING task belongs to a prior (dead) process — requeue
    # it (attempt++) so it is retried immediately, or fail it once retries are
    # exhausted. (older_than=0: at boot this process owns no in-flight task.)
    async with PostgresUnitOfWork(session_maker) as uow:
        await recover_running_tasks(uow)
    interval = float(os.environ.get("AEGIS_AGENT_RUNTIME_POLL_SECONDS", "1.0"))
    orphan_lease_seconds = _orphan_lease_seconds()
    logger.info(
        "Agent runtime worker started",
        extra={
            "pollIntervalSeconds": interval,
            "orphanLeaseSeconds": orphan_lease_seconds,
            "taskTimeoutSeconds": _resolve_task_timeout_seconds(),
        },
    )

    async def poll() -> int:
        return await _poll_once(
            session_maker,
            executor,
            orphan_lease_seconds=orphan_lease_seconds,
            stop_event=stop_event,
        )

    try:
        await _run_poll_loop(poll, stop_event, interval=interval)
    finally:
        logger.info("Agent runtime worker stopped")
        await dispose_engine(engine)


async def _amain() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler is unavailable on some platforms (e.g. Windows);
            # fall back to the signal module, which only sets a cooperative flag.
            signal.signal(sig, lambda _signum, _frame: stop_event.set())
    await _run_loop(stop_event)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
