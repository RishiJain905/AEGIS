"""Recover orphaned agent tasks (worker crash / restart, or stranded claims).

The executor commits the QUEUED->RUNNING claim early (so the model call holds no
per-run advisory lock and cannot freeze the tick engine). The trade-off is that a
worker crash — or any code path that strands a claimed task — leaves the task in
'running' with no in-band rollback. This module reclaims such tasks:

* a RUNNING task whose claim (``started_at``) is older than ``older_than_seconds``
  is treated as orphaned (no live executor is working it — a healthy task reaches a
  terminal state via the executor's own timeout well before the threshold),
* orphans under the attempt cap are requeued (attempt incremented) so the normal
  runtime re-executes them,
* orphans at the attempt cap are marked TIMED_OUT terminally, with a
  ``agent.task.failed`` event and (incident-scoped only) a terminal session.

All writes use the atomic ``claim_transition`` CAS out of 'running', so a task the
executor is concurrently completing is never clobbered (the CAS simply finds no
row and the reclaim is skipped).
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.errors import AgentRuntimeErrorCode
from aegis_agents.runtime.events import build_task_completed_event
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.session_service import AgentSessionService, _run_sim_time
from aegis_agents.runtime.state_machine import can_transition
from aegis_contracts.agent_runtime import AgentTaskStatus, AgentTaskV1
from aegis_contracts.entities import AgentSessionState
from aegis_persistence.unit_of_work import PostgresUnitOfWork

# Mirror AgentTaskService.retry_task's cap (attempt >= 2 is non-retryable). The
# reclaim lease TTL lives in the worker (2x the task timeout); this only caps how
# many times an orphan is requeued before it is failed terminally.
DEFAULT_MAX_ATTEMPTS = 2


def _task_age_seconds(task: AgentTaskV1, now: datetime) -> float:
    anchor = task.started_at or task.updated_at
    return (now - anchor).total_seconds()


async def recover_orphaned_tasks(
    uow: PostgresUnitOfWork,
    *,
    older_than_seconds: float,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    sessions: AgentSessionService | None = None,
) -> int:
    """Reclaim orphaned RUNNING tasks; return how many were reclaimed.

    ``older_than_seconds=0`` reclaims every RUNNING task (startup recovery: a fresh
    process owns no in-flight task, so any 'running' row is a pre-restart orphan).
    A positive value scopes periodic recovery to tasks stranded past the timeout.
    """
    sessions = sessions or AgentSessionService()
    running = await uow.agent_tasks.list_running()
    now = datetime.now(UTC)
    reclaimed = 0
    for task in running:
        if _task_age_seconds(task, now) < older_than_seconds:
            continue
        if task.attempt < max_attempts:
            if await _requeue_orphan(uow, task, now):
                reclaimed += 1
        elif await _terminate_orphan(uow, task, now, sessions):
            reclaimed += 1
    return reclaimed


async def _requeue_orphan(uow: PostgresUnitOfWork, task: AgentTaskV1, now: datetime) -> bool:
    """Atomically return a stranded RUNNING task to QUEUED with attempt incremented."""
    requeued = task.model_copy(
        update={
            "status": AgentTaskStatus.QUEUED,
            "attempt": task.attempt + 1,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "error_code": None,
            "error_message": None,
        }
    )
    return await uow.agent_tasks.claim_transition(
        requeued, from_statuses=(AgentTaskStatus.RUNNING.value,)
    )


async def _terminate_orphan(
    uow: PostgresUnitOfWork,
    task: AgentTaskV1,
    now: datetime,
    sessions: AgentSessionService,
) -> bool:
    """Atomically fail an orphan that has exhausted its retries, with event + session."""
    timed_out = task.model_copy(
        update={
            "status": AgentTaskStatus.TIMED_OUT,
            "updated_at": now,
            "completed_at": now,
            "error_code": AgentRuntimeErrorCode.TASK_TIMEOUT.value,
            "error_message": "Orphaned running task reclaimed after exhausting retries",
        }
    )
    claimed = await uow.agent_tasks.claim_transition(
        timed_out, from_statuses=(AgentTaskStatus.RUNNING.value,)
    )
    if not claimed:
        return False
    # Incident-scoped sessions go terminal; run-scoped lane/chat sessions survive
    # (mirrors TaskExecutor._fail_task). Guarded so an already-terminal session
    # never raises.
    session = await uow.agent_sessions.get_by_id(task.session_id)
    if (
        session is not None
        and task.incident_id is not None
        and can_transition(session.state, AgentSessionState.FAILED)
    ):
        await sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.FAILED,
            reason="orphan_recovered",
            task_id=task.id,
            run_id=task.run_id,
        )
    next_sequence = await uow.events.next_sequence(task.run_id)
    await uow.append_event(
        build_task_completed_event(
            event_id=new_runtime_id("evt"),
            run_id=task.run_id,
            sequence=next_sequence,
            session_id=task.session_id,
            task_id=task.id,
            trace_id=task.trace_id,
            status=timed_out.status.value,
            sim_time=await _run_sim_time(uow, task.run_id),
        )
    )
    return True


async def recover_running_tasks(uow: PostgresUnitOfWork) -> int:
    """Startup recovery: reclaim every orphaned RUNNING task from a prior process.

    Retained for the worker's boot path and existing callers; delegates to
    :func:`recover_orphaned_tasks` with a zero age threshold (every RUNNING row is
    a pre-restart orphan), so a crashed-mid-task task is requeued (attempt++) and
    retried rather than silently failed.
    """
    return await recover_orphaned_tasks(uow, older_than_seconds=0.0)
