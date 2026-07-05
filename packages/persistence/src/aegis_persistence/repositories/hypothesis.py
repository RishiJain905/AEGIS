"""Phase 21 ORACLE hypothesis artifact persistence."""

from __future__ import annotations

from aegis_contracts import HypothesisV1
from aegis_contracts.hypothesis import (
    HypothesisComparisonV1,
    HypothesisRevisionV1,
    VerificationRequestV1,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import (
    domain_to_payload,
    hypothesis_comparison_to_domain,
    hypothesis_revision_to_domain,
    hypothesis_to_domain,
    verification_request_to_domain,
)
from aegis_persistence.orm.tables import (
    HypothesisComparisonRow,
    HypothesisRevisionRow,
    HypothesisRow,
    VerificationRequestRow,
)


class PostgresOracleHypothesisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_hypothesis(self, hypothesis: HypothesisV1) -> HypothesisV1:
        payload = domain_to_payload(hypothesis)
        row = HypothesisRow(
            id=hypothesis.id,
            incident_id=hypothesis.incident_id,
            payload=payload,
            created_at=hypothesis.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return hypothesis

    async def get_hypothesis(self, hypothesis_id: str) -> HypothesisV1 | None:
        row = await self._session.get(HypothesisRow, hypothesis_id)
        return hypothesis_to_domain(row) if row else None

    async def list_hypotheses_for_incident(self, incident_id: str) -> list[HypothesisV1]:
        result = await self._session.execute(
            select(HypothesisRow)
            .where(HypothesisRow.incident_id == incident_id)
            .order_by(HypothesisRow.created_at.asc())
        )
        return [hypothesis_to_domain(row) for row in result.scalars().all()]

    async def update_hypothesis(self, hypothesis: HypothesisV1) -> HypothesisV1:
        row = await self._session.get(HypothesisRow, hypothesis.id)
        if row is None:
            msg = f"Hypothesis not found: {hypothesis.id}"
            raise KeyError(msg)
        row.payload = domain_to_payload(hypothesis)
        await self._session.flush()
        return hypothesis

    async def add_revision(self, revision: HypothesisRevisionV1) -> HypothesisRevisionV1:
        row = HypothesisRevisionRow(
            id=revision.id,
            hypothesis_id=revision.hypothesis_id,
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

    async def list_revisions_for_hypothesis(
        self,
        hypothesis_id: str,
    ) -> list[HypothesisRevisionV1]:
        result = await self._session.execute(
            select(HypothesisRevisionRow)
            .where(HypothesisRevisionRow.hypothesis_id == hypothesis_id)
            .order_by(HypothesisRevisionRow.revision_number.asc())
        )
        return [hypothesis_revision_to_domain(row) for row in result.scalars().all()]

    async def list_revisions_for_incident(self, incident_id: str) -> list[HypothesisRevisionV1]:
        result = await self._session.execute(
            select(HypothesisRevisionRow)
            .where(HypothesisRevisionRow.incident_id == incident_id)
            .order_by(HypothesisRevisionRow.created_at.asc())
        )
        return [hypothesis_revision_to_domain(row) for row in result.scalars().all()]

    async def add_comparison(
        self,
        comparison: HypothesisComparisonV1,
    ) -> HypothesisComparisonV1:
        row = HypothesisComparisonRow(
            id=comparison.id,
            incident_id=comparison.incident_id,
            session_id=comparison.session_id,
            task_id=comparison.task_id,
            payload=domain_to_payload(comparison),
            created_at=comparison.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return comparison

    async def list_comparisons_for_incident(
        self,
        incident_id: str,
    ) -> list[HypothesisComparisonV1]:
        result = await self._session.execute(
            select(HypothesisComparisonRow)
            .where(HypothesisComparisonRow.incident_id == incident_id)
            .order_by(HypothesisComparisonRow.created_at.asc())
        )
        return [hypothesis_comparison_to_domain(row) for row in result.scalars().all()]

    async def add_verification_request(
        self,
        request: VerificationRequestV1,
    ) -> VerificationRequestV1:
        row = VerificationRequestRow(
            id=request.id,
            incident_id=request.incident_id,
            hypothesis_id=request.hypothesis_id,
            session_id=request.session_id,
            task_id=request.task_id,
            idempotency_key=request.idempotency_key,
            payload=domain_to_payload(request),
            created_at=request.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return request

    async def get_verification_by_idempotency(
        self,
        incident_id: str,
        idempotency_key: str,
    ) -> VerificationRequestV1 | None:
        result = await self._session.execute(
            select(VerificationRequestRow).where(
                VerificationRequestRow.incident_id == incident_id,
                VerificationRequestRow.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return verification_request_to_domain(row) if row else None

    async def list_verification_requests(
        self,
        incident_id: str,
    ) -> list[VerificationRequestV1]:
        result = await self._session.execute(
            select(VerificationRequestRow)
            .where(VerificationRequestRow.incident_id == incident_id)
            .order_by(VerificationRequestRow.created_at.asc())
        )
        return [verification_request_to_domain(row) for row in result.scalars().all()]
