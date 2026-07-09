"""Phase 24 approval and executed-action persistence."""

from __future__ import annotations

from aegis_contracts import ApprovalV1, ExecutedActionV1
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import (
    approval_to_domain,
    domain_to_payload,
    executed_action_to_domain,
)
from aegis_persistence.orm.tables import ApprovalRow, ExecutedActionRow


class PostgresApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, approval: ApprovalV1) -> ApprovalV1:
        row = ApprovalRow(
            id=approval.id,
            proposal_id=approval.proposal_id,
            payload=domain_to_payload(approval),
            decided_at=approval.decided_at,
        )
        self._session.add(row)
        await self._session.flush()
        return approval

    async def get_by_id(self, approval_id: str) -> ApprovalV1 | None:
        row = await self._session.get(ApprovalRow, approval_id)
        return approval_to_domain(row) if row else None

    async def list_for_proposal(self, proposal_id: str) -> list[ApprovalV1]:
        result = await self._session.execute(
            select(ApprovalRow)
            .where(ApprovalRow.proposal_id == proposal_id)
            .order_by(ApprovalRow.decided_at.asc())
        )
        return [approval_to_domain(row) for row in result.scalars().all()]

    async def list_for_incident(self, incident_id: str) -> list[ApprovalV1]:
        from aegis_persistence.orm.tables import ActionProposalRow

        result = await self._session.execute(
            select(ApprovalRow)
            .join(ActionProposalRow, ActionProposalRow.id == ApprovalRow.proposal_id)
            .where(ActionProposalRow.incident_id == incident_id)
            .order_by(ApprovalRow.decided_at.asc())
        )
        return [approval_to_domain(row) for row in result.scalars().all()]


class PostgresExecutedActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, action: ExecutedActionV1) -> ExecutedActionV1:
        row = ExecutedActionRow(
            id=action.id,
            proposal_id=action.proposal_id,
            run_id=action.run_id,
            idempotency_key=action.idempotency_key,
            payload=domain_to_payload(action),
            executed_at=action.executed_at,
        )
        self._session.add(row)
        await self._session.flush()
        return action

    async def get_by_id(self, action_id: str) -> ExecutedActionV1 | None:
        row = await self._session.get(ExecutedActionRow, action_id)
        return executed_action_to_domain(row) if row else None

    async def get_by_idempotency(
        self,
        *,
        run_id: str,
        idempotency_key: str,
    ) -> ExecutedActionV1 | None:
        result = await self._session.execute(
            select(ExecutedActionRow).where(
                ExecutedActionRow.run_id == run_id,
                ExecutedActionRow.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return executed_action_to_domain(row) if row else None

    async def list_for_proposal(self, proposal_id: str) -> list[ExecutedActionV1]:
        result = await self._session.execute(
            select(ExecutedActionRow)
            .where(ExecutedActionRow.proposal_id == proposal_id)
            .order_by(ExecutedActionRow.executed_at.asc())
        )
        return [executed_action_to_domain(row) for row in result.scalars().all()]

    async def list_for_incident(self, incident_id: str) -> list[ExecutedActionV1]:
        from aegis_persistence.orm.tables import ActionProposalRow

        result = await self._session.execute(
            select(ExecutedActionRow)
            .join(ActionProposalRow, ActionProposalRow.id == ExecutedActionRow.proposal_id)
            .where(ActionProposalRow.incident_id == incident_id)
            .order_by(ExecutedActionRow.executed_at.asc())
        )
        return [executed_action_to_domain(row) for row in result.scalars().all()]
