"""Autonomous triage service: bounded, RoE-gated auto-tasking on new evidence.

The service is the single enqueue path for all autonomous initiative (alert triage today;
standing directives and bias-guard reuse ``enqueue_auto_task``). It is deliberately
enqueue-only — it never runs the model — so it is safe to drive from a lightweight poller
and fully testable offline: a created task is QUEUED and executed later by the normal agent
runtime, where the RoE-encoded instructions steer any follow-up chaining.

Budgets (all env-tunable via :class:`AutonomyBudget`) cap local-model load:
* max concurrent (QUEUED/RUNNING) autonomy tasks per run,
* per-asset wall-clock cooldown (in-memory; sim-agnostic),
* hard per-run task cap.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from aegis_contracts import (
    AegisSettings,
    AgentRole,
    RulesOfEngagementV1,
    deterministic_incident_id,
)
from aegis_contracts.agent_runtime import (
    AgentTaskStatus,
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AutonomyInitiatorV1
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_persistence.sim_clock import run_sim_time
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_agents.autonomy.events import build_autonomy_task_enqueued_event
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService

_ACTIVE_STATUSES = {AgentTaskStatus.QUEUED, AgentTaskStatus.RUNNING}


@dataclass(frozen=True)
class AutonomyBudget:
    max_concurrent: int = 2
    per_asset_cooldown_seconds: float = 120.0
    max_per_run: int = 50

    @classmethod
    def from_settings(cls, settings: AegisSettings) -> AutonomyBudget:
        return cls(
            max_concurrent=settings.AEGIS_AUTONOMY_MAX_CONCURRENT_TASKS,
            per_asset_cooldown_seconds=settings.AEGIS_AUTONOMY_PER_ASSET_COOLDOWN_SECONDS,
            max_per_run=settings.AEGIS_AUTONOMY_MAX_TASKS_PER_RUN,
        )


def _watchtower_instructions(roe: RulesOfEngagementV1, alert_title: str, asset_id: str) -> str:
    base = (
        f"Autonomous triage: a new alert '{alert_title}' fired on {asset_id}. "
        "Assess severity and whether it is a real lead. Ground every claim in evidence. "
        "If nothing warrants attention, reply NO_CHANGE."
    )
    if roe == RulesOfEngagementV1.OBSERVE:
        return base + " Report only: do NOT chain further investigation or draft containment."
    if roe == RulesOfEngagementV1.INVESTIGATE:
        return (
            base
            + " If you find a concrete lead you MAY chain a single follow-up TRACE"
            " investigation. Do not draft containment."
        )
    return (
        base
        + " You may chain a follow-up TRACE investigation, and if confidence is high you MAY"
        " draft a BASTION containment proposal — it still requires policy validation and"
        " human approval before anything executes."
    )


def _directive_instructions(directive_text: str, alert_title: str, asset_id: str) -> str:
    return (
        f"Standing directive: {directive_text}\n"
        f"A new alert '{alert_title}' fired on {asset_id} within this directive's scope. "
        "Evaluate it against the directive and report anything that warrants the operator's "
        "attention. Ground every claim in evidence. If nothing does, reply NO_CHANGE."
    )


def _bias_guard_instructions(alert_title: str, asset_id: str) -> str:
    return (
        f"Bias guard: a new alert '{alert_title}' fired on {asset_id}, which overlaps assets "
        "already referenced by the leading hypotheses. Re-examine those leading hypotheses "
        "against this new evidence. Where the new evidence undermines a leading hypothesis, "
        "emit an explicit `contradicts` marker in your structured output naming the "
        "hypothesis. Ground every claim in evidence. If nothing changes, reply NO_CHANGE."
    )


@dataclass
class AutonomyTriageService:
    budget: AutonomyBudget = field(default_factory=AutonomyBudget)
    sessions: AgentSessionService = field(default_factory=AgentSessionService)
    tasks: AgentTaskService = field(default_factory=AgentTaskService)
    # In-memory, per long-lived process: a dedicated autonomy session per (run, role) so
    # different autonomous concerns land on the correct agent (WATCHTOWER triage/directives,
    # ORACLE bias-guard), and the last wall-clock enqueue time per (run, asset, role) for
    # cooldown so those concerns throttle independently. Mirrors the tick engine's in-memory
    # cursor: after a restart a fresh session is created and the cap resets.
    _session_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    _asset_cooldowns: dict[tuple[str, str, str], float] = field(default_factory=dict)

    async def on_new_alert(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        alert_id: str,
        asset_id: str,
        alert_title: str,
        roe: RulesOfEngagementV1,
        now: float | None = None,
    ) -> str | None:
        """Enqueue a WATCHTOWER triage task for a new alert, honouring RoE + budgets.

        Returns the enqueued task id, or None when a budget denied the enqueue. RoE never
        suppresses triage itself (even OBSERVE triages); it constrains what the task may
        chain, via the instructions.
        """
        instructions = _watchtower_instructions(roe, alert_title, asset_id)
        return await self.enqueue_auto_task(
            uow,
            run_id=run_id,
            role=AgentRole.WATCHTOWER,
            instructions=instructions,
            reason=f"alert:{alert_id}",
            alert_id=alert_id,
            asset_id=asset_id,
            incident_id=await self._existing_incident_for_asset(uow, run_id, asset_id),
            now=now,
        )

    @staticmethod
    async def _existing_incident_for_asset(
        uow: PostgresUnitOfWork, run_id: str, asset_id: str
    ) -> str | None:
        """The asset's already-open case, or None. Never opens one.

        WATCHTOWER enriches cases; it does not create them (ADR 0037 — the detection
        engine opens incidents deterministically, so incident existence survives a
        provider outage). Deliberately a lookup and not a resolve-or-create, mirroring
        ``OperatorActionService._require_incident``: a triage turn that could open a case
        would put incident existence back behind a model call.

        Returning None leaves the task run-scoped, which is exactly the pre-correlation
        behaviour — the alert simply has not crossed a correlation threshold yet.
        """
        incident_id = deterministic_incident_id(run_id, asset_id)
        incident = await uow.incidents.get_by_id(incident_id)
        return incident.id if incident is not None else None

    async def on_directive_match(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        directive_id: str,
        directive_text: str,
        alert_id: str,
        asset_id: str,
        alert_title: str,
        now: float | None = None,
    ) -> str | None:
        """Enqueue a WATCHTOWER task carrying a matched directive's text as instructions.

        Shares the run's WATCHTOWER autonomy lane (and its budget) with alert triage — so
        directives and triage draw from the same pool. ``asset_id`` is deliberately not
        passed to the cooldown gate: triage always fires first for the same alert and would
        otherwise suppress the directive on that asset. The shared WATCHTOWER concurrency cap
        still bounds directive load. Returns the task id, or None when a budget denied it.
        """
        return await self.enqueue_auto_task(
            uow,
            run_id=run_id,
            role=AgentRole.WATCHTOWER,
            instructions=_directive_instructions(directive_text, alert_title, asset_id),
            reason=f"directive:{directive_id}",
            alert_id=alert_id,
            asset_id=None,
            now=now,
        )

    async def on_bias_guard(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        alert_id: str,
        asset_id: str,
        alert_title: str,
        now: float | None = None,
    ) -> str | None:
        """Enqueue an ORACLE re-examination when a new alert overlaps hypothesis assets.

        Runs on the run's dedicated ORACLE autonomy lane (separate budget from triage), so a
        burst of overlapping alerts cannot starve WATCHTOWER triage. Returns the task id or
        None on a budget denial.
        """
        return await self.enqueue_auto_task(
            uow,
            run_id=run_id,
            role=AgentRole.ORACLE,
            instructions=_bias_guard_instructions(alert_title, asset_id),
            reason=f"bias-guard:{alert_id}",
            alert_id=alert_id,
            asset_id=asset_id,
            now=now,
        )

    async def enqueue_auto_task(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        role: AgentRole,
        instructions: str,
        reason: str,
        alert_id: str | None = None,
        asset_id: str | None = None,
        incident_id: str | None = None,
        now: float | None = None,
    ) -> str | None:
        wall = now if now is not None else time.monotonic()
        if asset_id is not None and self._asset_on_cooldown(run_id, asset_id, role, wall):
            return None

        session_id = await self._ensure_autonomy_session(uow, run_id, role)
        existing = await uow.agent_tasks.list_for_session(session_id)
        if len(existing) >= self.budget.max_per_run:
            return None
        active = sum(1 for task in existing if task.status in _ACTIVE_STATUSES)
        if active >= self.budget.max_concurrent:
            return None

        session = await uow.agent_sessions.get_by_id(session_id)
        if session is None:  # session evicted between ensure and now; recreate next call
            self._session_ids.pop((run_id, role.value), None)
            return None
        task = await self.tasks.create_task(
            uow,
            session=session,
            request=CreateAgentTaskRequestV1(
                schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                idempotency_key=f"autonomy-{reason}-{new_runtime_id('atk')}",
                instructions=instructions,
                initiator=AutonomyInitiatorV1.AUTONOMY,
            ),
            # Scoped to the case the detection engine already opened for this asset (when
            # there is one), so the turn's role post-processing lands on that incident.
            # The lane session itself stays run-scoped and shared.
            incident_id=incident_id,
        )
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_autonomy_task_enqueued_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session_id,
                task_id=task.id,
                trace_id=session.trace_id,
                role=role.value,
                reason=reason,
                alert_id=alert_id,
                asset_id=asset_id,
                # ``wall`` above drives cooldowns (real elapsed time); the event's place in
                # the chronicle is the run's virtual clock.
                sim_time=await run_sim_time(uow, run_id),
            )
        )
        if asset_id is not None:
            self._asset_cooldowns[(run_id, asset_id, role.value)] = wall
        return task.id

    def _asset_on_cooldown(
        self, run_id: str, asset_id: str, role: AgentRole, wall: float
    ) -> bool:
        last = self._asset_cooldowns.get((run_id, asset_id, role.value))
        if last is None:
            return False
        return (wall - last) < self.budget.per_asset_cooldown_seconds

    async def _ensure_autonomy_session(
        self, uow: PostgresUnitOfWork, run_id: str, role: AgentRole
    ) -> str:
        key = (run_id, role.value)
        cached = self._session_ids.get(key)
        if cached is not None and await uow.agent_sessions.get_by_id(cached) is not None:
            return cached
        session = await self.sessions.create_run_session(
            uow,
            run_id=run_id,
            request=CreateAgentSessionRequestV1(
                schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
                role=role,
                trace_id=new_runtime_id("trc"),
                enqueue_initial_task=False,
            ),
            # Background triage the worker opened on its own initiative. Marking the
            # session (not just its tasks) keeps these threads out of the operator's
            # copilot, which otherwise showed conversations nobody started.
            origin=AutonomyInitiatorV1.AUTONOMY,
        )
        self._session_ids[key] = session.id
        return session.id
