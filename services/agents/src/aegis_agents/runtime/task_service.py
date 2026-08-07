"""Agent task queue and idempotency service."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY, AgentDefinitionRegistry
from aegis_contracts.agent_runtime import AgentTaskStatus, AgentTaskV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentSessionV1
from aegis_contracts.versioning import AGENT_TASK_SCHEMA_VERSION
from aegis_persistence.errors import DuplicateIdempotencyKeyError
from aegis_persistence.unit_of_work import PostgresUnitOfWork


def _configured_default_provider_id() -> str:
    """The provider a task uses when the request doesn't pin one.

    Resolves to the deployment's ``AEGIS_PROVIDER_DEFAULT`` (e.g. the local
    ``openai-compatible`` model that backs the copilot) rather than a hardcoded
    ``mock``, so the running app actually engages the configured model. Falls back
    to ``mock`` if provider settings can't be loaded (keeps CI/offline safe).
    """
    try:
        from aegis_model_provider import load_provider_settings

        return load_provider_settings().AEGIS_PROVIDER_DEFAULT.value
    except Exception:  # noqa: BLE001
        return "mock"


async def _run_pinned_provider_id(uow: PostgresUnitOfWork, run_id: str) -> str | None:
    """The provider the run's loadout fixed for every generation it causes, if any.

    ``None`` for every run launched before the loadout could name one, and for the local
    default — both of which fall through to the deployment default unchanged.
    """
    run = await uow.runs.get_by_id(run_id)
    loadout = getattr(run, "loadout", None) if run is not None else None
    return getattr(loadout, "provider_id", None) if loadout is not None else None


class AgentTaskService:
    def __init__(self, registry: AgentDefinitionRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_AGENT_REGISTRY

    async def create_task(
        self,
        uow: PostgresUnitOfWork,
        *,
        session: AgentSessionV1,
        request: CreateAgentTaskRequestV1,
        incident_id: str | None = None,
    ) -> AgentTaskV1:
        """Queue a task on ``session``.

        ``incident_id`` scopes a single task to a case its session is not bound to. That
        is what lets the autonomy lanes — one long-lived run-scoped session per (run,
        role) — enrich the case the detection engine already opened for an alerting
        asset: the executor keys role post-processing off ``task.incident_id``, so
        without this an autonomy triage turn could never write to an incident. Defaults
        to the session's own incident, which is every other caller's behaviour.
        """
        # Provider precedence: the run's loadout, then the request, then the deployment
        # default. The loadout outranks the request deliberately. Run creation is where a
        # cloud provider is checked against the owner's stored credential, so letting a
        # per-task ``providerId`` override the run's would make that check bypassable by
        # anyone who can task an agent. Resolving it here rather than in each caller means
        # every enqueue path — operator chat, autonomy lanes, harnesses — inherits it.
        provider_id = (
            await _run_pinned_provider_id(uow, session.run_id)
            or request.provider_id
            or _configured_default_provider_id()
        )
        now = datetime.now(UTC)
        existing = await uow.agent_tasks.get_by_idempotency(
            session_id=session.id,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None:
            return existing
        task = AgentTaskV1(
            schema_version=AGENT_TASK_SCHEMA_VERSION,
            id=new_runtime_id("atk"),
            session_id=session.id,
            run_id=session.run_id,
            incident_id=incident_id or session.incident_id,
            status=AgentTaskStatus.QUEUED,
            attempt=1,
            idempotency_key=request.idempotency_key,
            trace_id=session.trace_id,
            provider_id=provider_id,
            instructions=request.instructions,
            initiator=request.initiator,
            created_at=now,
            updated_at=now,
        )
        try:
            return await uow.agent_tasks.add(task)
        except DuplicateIdempotencyKeyError:
            await uow.session.rollback()
            existing = await uow.agent_tasks.get_by_idempotency(
                session_id=session.id,
                idempotency_key=request.idempotency_key,
            )
            if existing is None:
                raise
            return existing

    async def get_task(self, uow: PostgresUnitOfWork, task_id: str) -> AgentTaskV1:
        task = await uow.agent_tasks.get_by_id(task_id)
        if task is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TASK_NOT_FOUND,
                message=f"Agent task not found: {task_id}",
            )
        return task

    async def retry_task(self, uow: PostgresUnitOfWork, task_id: str) -> AgentTaskV1:
        task = await self.get_task(uow, task_id)
        if task.status not in {AgentTaskStatus.FAILED, AgentTaskStatus.TIMED_OUT}:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.INVALID_TRANSITION,
                message=f"Task {task_id} is not retryable from status {task.status.value}",
                details={"status": task.status.value},
                trace_id=task.trace_id,
            )
        if task.attempt >= 2:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.INVALID_TRANSITION,
                message="Maximum retry attempts exceeded",
                details={"attempt": task.attempt},
                trace_id=task.trace_id,
            )
        now = datetime.now(UTC)
        retried = task.model_copy(
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
        # Atomic requeue: only one concurrent retry may transition a terminal
        # (FAILED/TIMED_OUT) task back to QUEUED, so a task cannot be requeued
        # twice (and the attempt counter cannot be double-incremented).
        claimed = await uow.agent_tasks.claim_transition(
            retried,
            from_statuses=(AgentTaskStatus.FAILED.value, AgentTaskStatus.TIMED_OUT.value),
        )
        if not claimed:
            current = await uow.agent_tasks.get_by_id(task_id)
            if current is None:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.TASK_NOT_FOUND,
                    message=f"Agent task not found: {task_id}",
                )
            return current
        return retried
