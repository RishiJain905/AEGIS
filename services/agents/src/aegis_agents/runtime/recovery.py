"""Recover interrupted agent tasks after process restart."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.errors import AgentRuntimeErrorCode
from aegis_contracts.agent_runtime import AgentTaskStatus
from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def recover_running_tasks(uow: PostgresUnitOfWork) -> int:
    """Mark orphaned running tasks as failed so they can be retried explicitly."""
    running = await uow.agent_tasks.list_running()
    now = datetime.now(UTC)
    recovered = 0
    for task in running:
        failed = task.model_copy(
            update={
                "status": AgentTaskStatus.FAILED,
                "updated_at": now,
                "completed_at": now,
                "error_code": AgentRuntimeErrorCode.INTERNAL.value,
                "error_message": "Recovered after process restart",
            }
        )
        await uow.agent_tasks.update(failed)
        recovered += 1
    return recovered
