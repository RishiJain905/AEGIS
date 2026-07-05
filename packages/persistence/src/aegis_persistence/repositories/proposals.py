"""Phase 22 BASTION/WARDEN proposal and policy artifact persistence."""

from __future__ import annotations

from aegis_contracts import ActionProposalV1
from aegis_contracts.proposals import PolicyDecisionV1, ProposalRevisionV1
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import (
    action_proposal_to_domain,
    domain_to_payload,
    policy_decision_to_domain,
    proposal_revision_to_domain,
)
from aegis_persistence.orm.tables import (
    ActionProposalRow,
    PolicyDecisionRow,
    ProposalRevisionRow,
)


class PostgresProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_proposal(self, proposal: ActionProposalV1) -> ActionProposalV1:
        payload = domain_to_payload(proposal)
        row = ActionProposalRow(
            id=proposal.id,
            incident_id=proposal.incident_id,
            revision=proposal.revision,
            status=proposal.status.value,
            payload=payload,
            created_at=proposal.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return proposal

    async def get_proposal(self, proposal_id: str) -> ActionProposalV1 | None:
        row = await self._session.get(ActionProposalRow, proposal_id)
        return action_proposal_to_domain(row) if row else None

    async def update_proposal(self, proposal: ActionProposalV1) -> ActionProposalV1:
        row = await self._session.get(ActionProposalRow, proposal.id)
        if row is None:
            msg = f"Proposal not found: {proposal.id}"
            raise KeyError(msg)
        row.revision = proposal.revision
        row.status = proposal.status.value
        row.payload = domain_to_payload(proposal)
        await self._session.flush()
        return proposal

    async def list_proposals_for_incident(self, incident_id: str) -> list[ActionProposalV1]:
        result = await self._session.execute(
            select(ActionProposalRow)
            .where(ActionProposalRow.incident_id == incident_id)
            .order_by(ActionProposalRow.created_at.asc())
        )
        return [action_proposal_to_domain(row) for row in result.scalars().all()]

    async def add_revision(self, revision: ProposalRevisionV1) -> ProposalRevisionV1:
        row = ProposalRevisionRow(
            id=revision.id,
            proposal_id=revision.proposal_id,
            incident_id=revision.incident_id,
            session_id=revision.session_id,
            task_id=revision.task_id,
            revision_number=revision.revision_number,
            payload=domain_to_payload(revision),
            created_at=revision.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return revision

    async def list_revisions_for_proposal(self, proposal_id: str) -> list[ProposalRevisionV1]:
        result = await self._session.execute(
            select(ProposalRevisionRow)
            .where(ProposalRevisionRow.proposal_id == proposal_id)
            .order_by(ProposalRevisionRow.revision_number.asc())
        )
        return [proposal_revision_to_domain(row) for row in result.scalars().all()]

    async def list_revisions_for_incident(self, incident_id: str) -> list[ProposalRevisionV1]:
        result = await self._session.execute(
            select(ProposalRevisionRow)
            .where(ProposalRevisionRow.incident_id == incident_id)
            .order_by(ProposalRevisionRow.created_at.asc())
        )
        return [proposal_revision_to_domain(row) for row in result.scalars().all()]

    async def get_revision(self, revision_id: str) -> ProposalRevisionV1 | None:
        row = await self._session.get(ProposalRevisionRow, revision_id)
        return proposal_revision_to_domain(row) if row else None

    async def add_policy_decision(self, decision: PolicyDecisionV1) -> PolicyDecisionV1:
        row = PolicyDecisionRow(
            id=decision.id,
            proposal_id=decision.proposal_id,
            proposal_revision_id=decision.proposal_revision_id,
            incident_id=decision.incident_id,
            session_id=decision.session_id,
            task_id=decision.task_id,
            payload=domain_to_payload(decision),
            evaluated_at=decision.evaluated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return decision

    async def list_policy_decisions_for_incident(
        self,
        incident_id: str,
    ) -> list[PolicyDecisionV1]:
        result = await self._session.execute(
            select(PolicyDecisionRow)
            .where(PolicyDecisionRow.incident_id == incident_id)
            .order_by(PolicyDecisionRow.evaluated_at.asc())
        )
        return [policy_decision_to_domain(row) for row in result.scalars().all()]

    async def list_policy_decisions_for_proposal(
        self,
        proposal_id: str,
    ) -> list[PolicyDecisionV1]:
        result = await self._session.execute(
            select(PolicyDecisionRow)
            .where(PolicyDecisionRow.proposal_id == proposal_id)
            .order_by(PolicyDecisionRow.evaluated_at.asc())
        )
        return [policy_decision_to_domain(row) for row in result.scalars().all()]
