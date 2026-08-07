"""Deterministic follow-up chaining for autonomous investigation turns.

Rules of engagement are a per-run operator dial (:class:`RulesOfEngagementV1` on the run's
loadout) whose meaning is already written into every autonomy prompt: OBSERVE reports only,
INVESTIGATE may chain one follow-up TRACE investigation, FORWARD_DEPLOYED may additionally
draft a containment proposal. Nothing in the tool allowlist ever let a model keep that
promise — chaining creates agent *sessions*, which is platform work and deliberately not a
model-visible tool — so an autonomous triage terminated at its own triage row. Every
downstream artifact the incident workspace renders (TRACE's evidence, plans, overlays and
candidate assets; ORACLE's hypotheses; BASTION's proposals) had exactly one producer: the
four operator trigger endpoints, which no product surface calls. The chain runs here
instead, deterministically, after the turn's own artifacts are persisted.

Bounded by construction:

* only autonomy-initiated turns chain, so the operator-triggered coordinators (which do
  their own enqueueing) are untouched and the ORACLE coordinator's TRACE follow-up cannot
  ping-pong against this;
* the follow-up idempotency key names the *incident and stage*, not the turn, so however
  many triage turns land on one case it gets at most one TRACE, one ORACLE, one BASTION
  and one WARDEN for the whole run;
* each stage re-checks the precondition its own coordinator enforces (evidence before
  ORACLE, hypotheses before BASTION) rather than enqueueing a turn that would fail on
  arrival.

Enqueue-only, exactly like :mod:`aegis_agents.autonomy.service`: the follow-up is QUEUED
and the normal agent runtime executes it later, so no model call ever happens inside the
caller's transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aegis_contracts import RulesOfEngagementV1
from aegis_contracts.agent_runtime import (
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AgentRole, AutonomyInitiatorV1
from aegis_contracts.investigation import TriageEscalationLevel
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_persistence.orm.tables import AgentTaskRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aegis_agents.runtime.session_service import AgentSessionService
    from aegis_agents.runtime.task_service import AgentTaskService

# Ordered, so a gate can ask "at least INVESTIGATE" without enumerating tiers.
_ROE_RANK: dict[RulesOfEngagementV1, int] = {
    RulesOfEngagementV1.OBSERVE: 0,
    RulesOfEngagementV1.INVESTIGATE: 1,
    RulesOfEngagementV1.FORWARD_DEPLOYED: 2,
}

_TRACE_INSTRUCTIONS = (
    "Autonomous follow-up: WATCHTOWER escalated this case. Investigate it within the "
    "hop and tool budget — expand the graph around the alerting assets, attach the "
    "evidence that supports or contradicts the escalation, and name the candidate "
    "affected assets. Ground every claim in visible evidence."
)

_ORACLE_INSTRUCTIONS = (
    "Autonomous follow-up: TRACE collected evidence for this case. Generate competing "
    "evidence-grounded hypotheses that explain it, preserve contradictions and unknowns, "
    "and state what would verify or falsify each one."
)

_BASTION_INSTRUCTIONS = (
    "Autonomous follow-up under forward-deployed rules of engagement: ORACLE has "
    "hypotheses for this case. Draft proportionate response options grounded in the "
    "evidence and hypotheses. Nothing executes — every proposal still passes deterministic "
    "policy validation and an explicit human approval."
)

_WARDEN_INSTRUCTIONS = (
    "Autonomous follow-up: explain the policy position on this case's proposals. Policy "
    "outcomes are computed deterministically by the platform; your prose is advisory."
)


def _stage_key(incident_id: str, stage: str) -> str:
    return f"autonomy-chain:{incident_id}:{stage}"


async def _run_roe(uow: PostgresUnitOfWork, run_id: str) -> RulesOfEngagementV1:
    """The run's dial, defaulting as :class:`AutonomyPoller` does for pre-loadout runs."""
    run = await uow.runs.get_by_id(run_id)
    if run is None or run.loadout is None:
        return RulesOfEngagementV1.INVESTIGATE
    return run.loadout.roe


@dataclass
class InvestigationChain:
    """Enqueues the next role in the investigation pipeline for autonomous turns.

    The session and task services are resolved on first use rather than imported at module
    scope: the role handlers that own a chain are themselves loaded from
    ``aegis_agents.roles.registry``, which the runtime registry imports, which the session
    service imports. Binding them eagerly closes that loop.
    """

    sessions: AgentSessionService | None = None
    tasks: AgentTaskService | None = None

    def _services(self) -> tuple[AgentSessionService, AgentTaskService]:
        if self.sessions is None or self.tasks is None:
            from aegis_agents.runtime.session_service import AgentSessionService
            from aegis_agents.runtime.task_service import AgentTaskService

            self.sessions = self.sessions or AgentSessionService()
            self.tasks = self.tasks or AgentTaskService()
        return self.sessions, self.tasks

    async def advance(
        self,
        uow: PostgresUnitOfWork,
        *,
        from_role: AgentRole,
        incident_id: str,
        run_id: str,
        trace_id: str,
        initiator: AutonomyInitiatorV1,
        escalation: TriageEscalationLevel | None = None,
    ) -> list[str]:
        """Enqueue whatever follows ``from_role`` for this case. Returns the task ids.

        Silent no-op on every gate — an operator-tasked turn, a case that has already been
        carried through this stage, a run whose RoE forbids it, or a missing precondition.
        A background turn declining to chain is the normal outcome, not a failure.
        """
        if initiator is not AutonomyInitiatorV1.AUTONOMY or not incident_id:
            return []
        roe = await _run_roe(uow, run_id)
        if _ROE_RANK[roe] < _ROE_RANK[RulesOfEngagementV1.INVESTIGATE]:
            return []  # OBSERVE reports only; it never chains.

        if from_role is AgentRole.WATCHTOWER:
            return await self._after_triage(
                uow, incident_id=incident_id, trace_id=trace_id, escalation=escalation
            )
        if from_role is AgentRole.TRACE:
            return await self._after_trace(uow, incident_id=incident_id, trace_id=trace_id)
        if from_role is AgentRole.ORACLE:
            return await self._after_oracle(
                uow, incident_id=incident_id, trace_id=trace_id, roe=roe
            )
        return []

    async def _after_triage(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        trace_id: str,
        escalation: TriageEscalationLevel | None,
    ) -> list[str]:
        # MONITOR is triage concluding there is nothing to investigate. Spending an
        # investigation turn on it would contradict the finding, and it is the same gate
        # ``WatchtowerCoordinator._enqueue_trace_session`` applies on the operator path.
        if escalation is TriageEscalationLevel.MONITOR:
            return []
        return await self._enqueue(
            uow,
            role=AgentRole.TRACE,
            incident_id=incident_id,
            trace_id=trace_id,
            stage="trace",
            instructions=_TRACE_INSTRUCTIONS,
        )

    async def _after_trace(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        trace_id: str,
    ) -> list[str]:
        # ORACLE reasons over evidence; with none attached it has nothing to be grounded
        # in and its grounding validator would reject whatever it invented.
        evidence = await uow.investigation.list_evidence_attachments(incident_id)
        if not evidence:
            return []
        return await self._enqueue(
            uow,
            role=AgentRole.ORACLE,
            incident_id=incident_id,
            trace_id=trace_id,
            stage="oracle",
            instructions=_ORACLE_INSTRUCTIONS,
        )

    async def _after_oracle(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        trace_id: str,
        roe: RulesOfEngagementV1,
    ) -> list[str]:
        # Drafting containment is the one step INVESTIGATE withholds.
        if _ROE_RANK[roe] < _ROE_RANK[RulesOfEngagementV1.FORWARD_DEPLOYED]:
            return []
        # The precondition ``BastionCoordinator`` raises on. Here it is a gate rather than
        # an error: no hypotheses simply means this case is not ready for a response.
        hypotheses = await uow.oracle_hypotheses.list_hypotheses_for_incident(incident_id)
        if not hypotheses:
            return []
        enqueued = await self._enqueue(
            uow,
            role=AgentRole.BASTION,
            incident_id=incident_id,
            trace_id=trace_id,
            stage="bastion",
            instructions=_BASTION_INSTRUCTIONS,
        )
        if not enqueued:
            return []
        # WARDEN alongside BASTION, matching ``BastionCoordinator``: it is queued second,
        # and the runtime drains in creation order, so it reads proposals that exist.
        enqueued += await self._enqueue(
            uow,
            role=AgentRole.WARDEN,
            incident_id=incident_id,
            trace_id=trace_id,
            stage="bastion-warden",
            instructions=_WARDEN_INSTRUCTIONS,
        )
        return enqueued

    async def _enqueue(
        self,
        uow: PostgresUnitOfWork,
        *,
        role: AgentRole,
        incident_id: str,
        trace_id: str,
        stage: str,
        instructions: str,
    ) -> list[str]:
        key = _stage_key(incident_id, stage)
        if await self._stage_already_run(uow, incident_id, key):
            return []
        sessions, tasks = self._services()
        session = await sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
                role=role,
                trace_id=trace_id,
                enqueue_initial_task=False,
            ),
            # Background initiative, like the lane that started it: marking the session
            # keeps these threads out of the operator's copilot.
            origin=AutonomyInitiatorV1.AUTONOMY,
        )
        task = await tasks.create_task(
            uow,
            session=session,
            request=CreateAgentTaskRequestV1(
                schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                idempotency_key=key,
                instructions=instructions,
                # Carries the chain forward, and buys the turn the same fail-soft tool
                # handling the lane gets: nobody is watching a background investigation.
                initiator=AutonomyInitiatorV1.AUTONOMY,
            ),
        )
        return [task.id]

    @staticmethod
    async def _stage_already_run(
        uow: PostgresUnitOfWork, incident_id: str, key: str
    ) -> bool:
        """Has this case already been carried through this stage?

        Keyed on the incident rather than the session, because the whole point is that a
        second triage turn on the same case must not open a second investigation.
        ``AgentTaskService.create_task`` only dedupes within one session, which would not
        see the earlier chain's session at all.
        """
        result = await uow.session.execute(
            select(AgentTaskRow.id).where(
                AgentTaskRow.incident_id == incident_id,
                AgentTaskRow.idempotency_key == key,
            )
        )
        return result.first() is not None
