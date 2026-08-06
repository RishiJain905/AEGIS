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
from aegis_contracts.agent_runtime import (
    AgentArtifactType,
    AgentArtifactV1,
    AgentTaskStatus,
    AgentTaskV1,
)
from aegis_contracts.entities import AgentSessionState
from aegis_contracts.versioning import AGENT_ARTIFACT_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork

# Mirror AgentTaskService.retry_task's cap (attempt >= 2 is non-retryable). The
# reclaim lease TTL lives in the worker (2x the task timeout); this only caps how
# many times an orphan is requeued before it is failed terminally.
DEFAULT_MAX_ATTEMPTS = 2


def _task_age_seconds(task: AgentTaskV1, now: datetime) -> float:
    """Seconds since this task last showed a sign of life.

    Anchored on ``updated_at``, which the executor's heartbeat refreshes every few
    seconds for as long as it is genuinely working the task (see
    ``TaskExecutor._heartbeat``). ``started_at`` — the previous anchor — only ever
    said when the claim happened, so it aged identically whether the executor was
    thinking or had died in the meantime; a task really being worked and a task
    abandoned mid-flight were indistinguishable. ``updated_at`` is never older
    than ``started_at`` (the claim writes both), so this is strictly the better
    signal even for a task whose heartbeat never got to run.
    """
    return (now - task.updated_at).total_seconds()


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
    # The CAS out of 'running' is what makes everything below run exactly once —
    # a second sweep (or a racing worker) finds no row and returns here — so the
    # artifact needs no idempotency key of its own.
    #
    # It exists because a terminated orphan otherwise produces a task that simply
    # stops, with nothing in the session for the operator to read. The turn's
    # panel shows artifacts; without one, a swept task looks the same as a task
    # still thinking, which is the confusion this whole path is meant to end.
    await uow.agent_artifacts.add(
        AgentArtifactV1(
            schema_version=AGENT_ARTIFACT_SCHEMA_VERSION,
            id=new_runtime_id("aaf"),
            task_id=task.id,
            session_id=task.session_id,
            artifact_type=AgentArtifactType.AUDIT,
            payload={
                "outcome": "task_timeout",
                "reason": "stale_running_task_swept",
                "detail": (
                    "This turn was abandoned by its executor and never reached a "
                    "terminal state on its own. It was failed by the stale-task "
                    "sweep after exceeding its timeout with no sign of life."
                ),
                "attempt": task.attempt,
                "staleForSeconds": round(_task_age_seconds(task, now), 1),
                "lastHeartbeatAt": task.updated_at.isoformat(),
            },
            created_at=now,
        )
    )
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


async def finalize_tasks_for_stopped_run(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    sessions: AgentSessionService | None = None,
) -> int:
    """Cancel every in-flight agent task on a run that has just stopped.

    A run that ends with tasks still queued or running leaves the copilot cards
    spinning with no honest terminal state — the operator cannot tell whether to
    wait, and the run is over, so no queued task will ever be useful and no
    running task's answer can change anything. Both are cancelled terminally with
    an attributable reason, and each cancellation is recorded in the run's event
    stream like any other task outcome (so the replay and the after-action see
    it). Returns how many tasks were cancelled.

    Every transition is the same status-guarded CAS the executor uses, so a task
    the worker is concurrently completing is never clobbered (the CAS finds no
    row and the cancellation is skipped) — and, symmetrically, the executor's own
    terminal writes are CAS-guarded, so a cancelled task is never resurrected by
    a late completion. Incident-scoped sessions go terminal (CANCELLED, mirroring
    ``TaskExecutor._fail_task``); run-scoped lane/chat sessions survive, because
    they host many turns and the operator still reads their history.
    """
    sessions = sessions or AgentSessionService()
    now = datetime.now(UTC)
    in_flight = await uow.agent_tasks.list_for_run(
        run_id,
        statuses=(AgentTaskStatus.QUEUED.value, AgentTaskStatus.RUNNING.value),
    )
    cancelled = 0
    for task in in_flight:
        message = (
            "Run stopped before the task started"
            if task.status == AgentTaskStatus.QUEUED
            else "Run stopped while the task was in flight"
        )
        terminal = task.model_copy(
            update={
                "status": AgentTaskStatus.CANCELLED,
                "updated_at": now,
                "completed_at": now,
                "error_code": AgentRuntimeErrorCode.TASK_CANCELLED.value,
                "error_message": message,
            }
        )
        claimed = await uow.agent_tasks.claim_transition(
            terminal, from_statuses=(task.status.value,)
        )
        if not claimed:
            # The executor got there first (or another finalizer did); its
            # terminal state stands and this cancellation is a no-op.
            continue
        cancelled += 1
        session = await uow.agent_sessions.get_by_id(task.session_id)
        if (
            session is not None
            and task.incident_id is not None
            and can_transition(session.state, AgentSessionState.CANCELLED)
        ):
            await sessions.transition(
                uow,
                session=session,
                to_state=AgentSessionState.CANCELLED,
                reason="run_stopped",
                task_id=task.id,
                run_id=run_id,
            )
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_task_completed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=task.session_id,
                task_id=task.id,
                trace_id=task.trace_id,
                status=AgentTaskStatus.CANCELLED.value,
                role=session.role.value if session is not None else None,
                error_code=AgentRuntimeErrorCode.TASK_CANCELLED.value,
                error_message=message,
                sim_time=await _run_sim_time(uow, run_id),
            )
        )
    return cancelled
