"""Investigation artifact persistence repositories."""

from __future__ import annotations

from aegis_contracts.investigation import (
    AgentGraphOverlayV1,
    CandidateAffectedAssetV1,
    EvidenceAttachmentV1,
    InvestigationDetailV1,
    InvestigationNoteV1,
    TraceInvestigationPlanV1,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import INVESTIGATION_DETAIL_SCHEMA_VERSION
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import (
    candidate_asset_to_domain,
    domain_to_payload,
    evidence_attachment_to_domain,
    graph_overlay_to_domain,
    investigation_note_to_domain,
    trace_plan_to_domain,
    triage_result_to_domain,
)
from aegis_persistence.orm.tables import (
    AgentGraphOverlayRow,
    CandidateAffectedAssetRow,
    EvidenceAttachmentRow,
    InvestigationNoteRow,
    TraceInvestigationPlanRow,
    WatchtowerTriageResultRow,
)
from aegis_persistence.repositories.hypothesis import PostgresOracleHypothesisRepository
from aegis_persistence.repositories.proposals import PostgresProposalRepository


class PostgresInvestigationRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        oracle_repository: PostgresOracleHypothesisRepository | None = None,
        proposal_repository: PostgresProposalRepository | None = None,
    ) -> None:
        self._session = session
        self._oracle = oracle_repository or PostgresOracleHypothesisRepository(session)
        self._proposals = proposal_repository or PostgresProposalRepository(session)

    async def get_triage_by_idempotency(
        self,
        incident_id: str,
        idempotency_key: str,
    ) -> WatchtowerTriageResultV1 | None:
        result = await self._session.execute(
            select(WatchtowerTriageResultRow).where(
                WatchtowerTriageResultRow.incident_id == incident_id,
                WatchtowerTriageResultRow.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return triage_result_to_domain(row) if row else None

    async def add_triage(self, triage: WatchtowerTriageResultV1) -> WatchtowerTriageResultV1:
        row = WatchtowerTriageResultRow(
            id=triage.id,
            incident_id=triage.incident_id,
            run_id=triage.run_id,
            session_id=triage.session_id,
            task_id=triage.task_id,
            idempotency_key=triage.idempotency_key,
            payload=domain_to_payload(triage),
            created_at=triage.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return triage

    async def list_triage_for_incident(self, incident_id: str) -> list[WatchtowerTriageResultV1]:
        result = await self._session.execute(
            select(WatchtowerTriageResultRow)
            .where(WatchtowerTriageResultRow.incident_id == incident_id)
            .order_by(WatchtowerTriageResultRow.created_at.asc())
        )
        return [triage_result_to_domain(row) for row in result.scalars().all()]

    async def add_plan(self, plan: TraceInvestigationPlanV1) -> TraceInvestigationPlanV1:
        row = TraceInvestigationPlanRow(
            id=plan.id,
            incident_id=plan.incident_id,
            session_id=plan.session_id,
            task_id=plan.task_id,
            payload=domain_to_payload(plan),
            created_at=plan.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return plan

    async def list_plans_for_incident(self, incident_id: str) -> list[TraceInvestigationPlanV1]:
        result = await self._session.execute(
            select(TraceInvestigationPlanRow)
            .where(TraceInvestigationPlanRow.incident_id == incident_id)
            .order_by(TraceInvestigationPlanRow.created_at.asc())
        )
        return [trace_plan_to_domain(row) for row in result.scalars().all()]

    async def add_evidence_attachment(
        self,
        attachment: EvidenceAttachmentV1,
    ) -> EvidenceAttachmentV1:
        row = EvidenceAttachmentRow(
            id=attachment.id,
            incident_id=attachment.incident_id,
            session_id=attachment.session_id,
            task_id=attachment.task_id,
            payload=domain_to_payload(attachment),
            created_at=attachment.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return attachment

    async def list_evidence_attachments(
        self,
        incident_id: str,
    ) -> list[EvidenceAttachmentV1]:
        result = await self._session.execute(
            select(EvidenceAttachmentRow)
            .where(EvidenceAttachmentRow.incident_id == incident_id)
            .order_by(EvidenceAttachmentRow.created_at.asc())
        )
        return [evidence_attachment_to_domain(row) for row in result.scalars().all()]

    async def add_note(self, note: InvestigationNoteV1) -> InvestigationNoteV1:
        row = InvestigationNoteRow(
            id=note.id,
            incident_id=note.incident_id,
            session_id=note.session_id,
            task_id=note.task_id,
            payload=domain_to_payload(note),
            created_at=note.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return note

    async def list_notes_for_incident(self, incident_id: str) -> list[InvestigationNoteV1]:
        result = await self._session.execute(
            select(InvestigationNoteRow)
            .where(InvestigationNoteRow.incident_id == incident_id)
            .order_by(InvestigationNoteRow.created_at.asc())
        )
        return [investigation_note_to_domain(row) for row in result.scalars().all()]

    async def add_candidate_asset(
        self,
        candidate: CandidateAffectedAssetV1,
    ) -> CandidateAffectedAssetV1:
        row = CandidateAffectedAssetRow(
            id=candidate.id,
            incident_id=candidate.incident_id,
            asset_id=candidate.asset_id,
            payload=domain_to_payload(candidate),
            created_at=candidate.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return candidate

    async def list_candidate_assets(
        self,
        incident_id: str,
    ) -> list[CandidateAffectedAssetV1]:
        result = await self._session.execute(
            select(CandidateAffectedAssetRow)
            .where(CandidateAffectedAssetRow.incident_id == incident_id)
            .order_by(CandidateAffectedAssetRow.created_at.asc())
        )
        return [candidate_asset_to_domain(row) for row in result.scalars().all()]

    async def add_graph_overlay(self, overlay: AgentGraphOverlayV1) -> AgentGraphOverlayV1:
        row = AgentGraphOverlayRow(
            id=overlay.id,
            incident_id=overlay.incident_id,
            run_id=overlay.run_id,
            session_id=overlay.session_id,
            task_id=overlay.task_id,
            payload=domain_to_payload(overlay),
            created_at=overlay.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return overlay

    async def list_graph_overlays(self, incident_id: str) -> list[AgentGraphOverlayV1]:
        result = await self._session.execute(
            select(AgentGraphOverlayRow)
            .where(AgentGraphOverlayRow.incident_id == incident_id)
            .order_by(AgentGraphOverlayRow.created_at.asc())
        )
        return [graph_overlay_to_domain(row) for row in result.scalars().all()]

    async def get_detail(self, incident_id: str, run_id: str) -> InvestigationDetailV1:
        return InvestigationDetailV1(
            schema_version=INVESTIGATION_DETAIL_SCHEMA_VERSION,
            incident_id=incident_id,
            run_id=run_id,
            triage_results=await self.list_triage_for_incident(incident_id),
            plans=await self.list_plans_for_incident(incident_id),
            evidence_attachments=await self.list_evidence_attachments(incident_id),
            notes=await self.list_notes_for_incident(incident_id),
            candidate_assets=await self.list_candidate_assets(incident_id),
            overlays=await self.list_graph_overlays(incident_id),
            hypotheses=await self._oracle.list_hypotheses_for_incident(incident_id),
            hypothesis_revisions=await self._oracle.list_revisions_for_incident(incident_id),
            hypothesis_comparisons=await self._oracle.list_comparisons_for_incident(incident_id),
            verification_requests=await self._oracle.list_verification_requests(incident_id),
            proposals=await self._proposals.list_proposals_for_incident(incident_id),
            proposal_revisions=await self._proposals.list_revisions_for_incident(incident_id),
            policy_decisions=await self._proposals.list_policy_decisions_for_incident(incident_id),
        )
