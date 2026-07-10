"""Phase 29 run score persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.parsing import parse_contract
from aegis_contracts.scoring import RunScoreV1
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import RunScoreRow


def run_score_to_domain(row: RunScoreRow) -> RunScoreV1:
    return parse_contract(RunScoreV1, row.payload)


class PostgresRunScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, score: RunScoreV1) -> RunScoreV1:
        payload = domain_to_payload(score)
        created_at = score.provenance.calculated_at
        if isinstance(created_at, str):
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created = created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        row = RunScoreRow(
            score_id=score.score_id,
            run_id=score.run_id,
            fingerprint=score.provenance.fingerprint,
            integrity_checksum=score.provenance.integrity_checksum,
            input_checksum=score.provenance.input_checksum,
            scenario_version=score.provenance.scenario_version,
            rubric_version=score.provenance.rubric_version,
            grading_engine_version=score.provenance.grading_engine_version,
            event_sequence_from=score.provenance.input_event_sequence_from,
            event_sequence_to=score.provenance.input_event_sequence_to,
            overall_score=score.overall_score,
            grade=score.grade.value if hasattr(score.grade, "value") else str(score.grade),
            payload=payload,
            created_at=created,
        )
        self._session.add(row)
        await self._session.flush()
        return score

    async def get_by_id(self, score_id: str) -> RunScoreV1 | None:
        row = await self._session.get(RunScoreRow, score_id)
        return run_score_to_domain(row) if row else None

    async def get_by_fingerprint(self, fingerprint: str) -> RunScoreV1 | None:
        result = await self._session.execute(
            select(RunScoreRow).where(RunScoreRow.fingerprint == fingerprint).limit(1)
        )
        row = result.scalar_one_or_none()
        return run_score_to_domain(row) if row else None

    async def get_latest_for_run(self, run_id: str) -> RunScoreV1 | None:
        result = await self._session.execute(
            select(RunScoreRow)
            .where(RunScoreRow.run_id == run_id)
            .order_by(RunScoreRow.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return run_score_to_domain(row) if row else None

    async def list_for_run(self, run_id: str) -> list[RunScoreV1]:
        result = await self._session.execute(
            select(RunScoreRow)
            .where(RunScoreRow.run_id == run_id)
            .order_by(RunScoreRow.created_at.asc())
        )
        return [run_score_to_domain(row) for row in result.scalars().all()]
