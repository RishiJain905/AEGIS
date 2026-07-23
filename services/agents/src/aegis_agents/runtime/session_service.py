"""Agent session lifecycle service."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.events import (
    build_session_started_event,
    build_session_state_changed_event,
)
from aegis_agents.runtime.ids import new_agent_session_id, new_runtime_id, new_transition_id
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY, AgentDefinitionRegistry
from aegis_agents.runtime.state_machine import assert_transition
from aegis_contracts import AgentSessionState, AgentSessionV1
from aegis_contracts.agent_runtime import (
    AgentSessionDetailV1,
    AgentStateTransitionV1,
    AgentTaskStatus,
    CreateAgentSessionRequestV1,
)
from aegis_contracts.versioning import (
    AGENT_SESSION_DETAIL_SCHEMA_VERSION,
    AGENT_SESSION_SCHEMA_VERSION,
    AGENT_STATE_TRANSITION_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork


class AgentSessionService:
    def __init__(self, registry: AgentDefinitionRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_AGENT_REGISTRY

    async def create_session(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        request: CreateAgentSessionRequestV1,
    ) -> AgentSessionV1:
        """Create an incident-scoped session (run_id derived from the incident)."""
        incident = await uow.incidents.get_by_id(incident_id)
        if incident is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.INCIDENT_NOT_FOUND,
                message=f"Incident not found: {incident_id}",
                trace_id=request.trace_id,
            )
        return await self._create(
            uow,
            run_id=incident.run_id,
            incident_id=incident_id,
            request=request,
        )

    async def create_run_session(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        request: CreateAgentSessionRequestV1,
    ) -> AgentSessionV1:
        """Create a run-scoped session (no incident yet). See ADR 0035.

        The caller is responsible for authorizing access to ``run_id`` and for
        confirming the run exists; this mirrors the other run-scoped routers,
        which resolve+authorize the run before invoking service logic.
        """
        return await self._create(
            uow, run_id=run_id, incident_id=None, request=request
        )

    async def _create(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        incident_id: str | None,
        request: CreateAgentSessionRequestV1,
    ) -> AgentSessionV1:
        definition = self._registry.get(request.role)
        if request.provider_id:
            definition = definition.model_copy(update={"provider_id": request.provider_id})
        now = datetime.now(UTC)
        session = AgentSessionV1(
            schema_version=AGENT_SESSION_SCHEMA_VERSION,
            id=new_agent_session_id(),
            run_id=run_id,
            incident_id=incident_id,
            role=request.role,
            state=AgentSessionState.QUEUED,
            trace_id=request.trace_id,
            created_at=now,
            updated_at=now,
        )
        await uow.agent_sessions.add(session, budget=definition.default_budget)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_session_started_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session.id,
                trace_id=session.trace_id,
                role=session.role.value,
            )
        )
        return session

    async def get_detail(self, uow: PostgresUnitOfWork, session_id: str) -> AgentSessionDetailV1:
        session = await uow.agent_sessions.get_by_id(session_id)
        if session is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.SESSION_NOT_FOUND,
                message=f"Agent session not found: {session_id}",
            )
        return AgentSessionDetailV1(
            schema_version=AGENT_SESSION_DETAIL_SCHEMA_VERSION,
            session=session,
            tasks=await uow.agent_tasks.list_for_session(session_id),
            transitions=await uow.agent_transitions.list_for_session(session_id),
            tool_invocations=await uow.tool_invocations.list_for_session(session_id),
            artifacts=await uow.agent_artifacts.list_for_session(session_id),
            budget=await uow.agent_sessions.get_budget(session_id),
        )

    async def list_details_for_run(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> list[AgentSessionDetailV1]:
        """Full detail for every session anchored to ``run_id`` (chat restore)."""
        sessions = await uow.agent_sessions.list_for_run(run_id)
        return [await self.get_detail(uow, session.id) for session in sessions]

    async def transition(
        self,
        uow: PostgresUnitOfWork,
        *,
        session: AgentSessionV1,
        to_state: AgentSessionState,
        reason: str,
        task_id: str | None,
        run_id: str,
    ) -> AgentSessionV1:
        assert_transition(session.state, to_state, trace_id=session.trace_id)
        now = datetime.now(UTC)
        from_state = session.state
        updated = session.model_copy(update={"state": to_state, "updated_at": now})
        await uow.agent_sessions.update(updated)
        transition = AgentStateTransitionV1(
            schema_version=AGENT_STATE_TRANSITION_SCHEMA_VERSION,
            id=new_transition_id(),
            session_id=session.id,
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            created_at=now,
        )
        await uow.agent_transitions.add(transition)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_session_state_changed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session.id,
                trace_id=session.trace_id,
                from_state=from_state,
                to_state=to_state,
                task_id=task_id,
                reason=reason,
            )
        )
        return updated

    async def cancel(self, uow: PostgresUnitOfWork, session_id: str) -> AgentSessionV1:
        detail = await self.get_detail(uow, session_id)
        session = detail.session
        if session.state in {
            AgentSessionState.COMPLETED,
            AgentSessionState.FAILED,
            AgentSessionState.CANCELLED,
        }:
            return session
        for task in detail.tasks:
            if task.status in {AgentTaskStatus.QUEUED, AgentTaskStatus.RUNNING}:
                cancelled = task.model_copy(
                    update={
                        "status": AgentTaskStatus.CANCELLED,
                        "updated_at": datetime.now(UTC),
                        "completed_at": datetime.now(UTC),
                        "error_code": AgentRuntimeErrorCode.TASK_CANCELLED.value,
                    }
                )
                await uow.agent_tasks.update(cancelled)
        return await self.transition(
            uow,
            session=session,
            to_state=AgentSessionState.CANCELLED,
            reason="session_cancelled",
            task_id=None,
            run_id=session.run_id,
        )
