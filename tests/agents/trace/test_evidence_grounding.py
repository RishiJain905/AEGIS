"""attach_evidence validation and contradiction preservation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.tools.context import ToolExecutionContext
from aegis_agents.tools.investigation.handlers import handle_attach_evidence
from aegis_contracts.errors import ContractValidationError
from aegis_contracts.investigation import EvidenceAttachmentV1
from aegis_contracts.versioning import EVIDENCE_ATTACHMENT_SCHEMA_VERSION

from tests.agents.trace.helpers import make_evidence_attachment


def _ctx(*, visible: set[str]) -> ToolExecutionContext:
    uow = MagicMock()
    uow.investigation = MagicMock()
    uow.investigation.add_evidence_attachment = AsyncMock(
        side_effect=lambda attachment: attachment
    )
    return ToolExecutionContext(
        uow=uow,
        session_id="agent-session:ags_synthetic_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        incident_id="incident:inc_synthetic_001",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        visible_evidence_ids=visible,
    )


@pytest.mark.asyncio
async def test_attach_evidence_rejects_invisible_existing_evidence_source() -> None:
    ctx = _ctx(visible={"evidence:evd_visible"})
    with pytest.raises(AgentRuntimeError) as exc:
        await handle_attach_evidence(
            ctx,
            {
                "provenance": {
                    "sourceType": "existing_evidence",
                    "sourceId": "evidence:evd_hidden",
                    "summary": "Hidden evidence",
                },
                "confidence": 0.7,
                "rationale": "Should fail grounding",
            },
        )
    assert exc.value.code == AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE


@pytest.mark.asyncio
async def test_attach_evidence_rejects_invisible_evidence_citation() -> None:
    ctx = _ctx(visible={"evidence:evd_visible"})
    with pytest.raises(AgentRuntimeError) as exc:
        await handle_attach_evidence(
            ctx,
            {
                "provenance": {
                    "sourceType": "existing_evidence",
                    "sourceId": "evidence:evd_visible",
                    "summary": "Visible source",
                },
                "evidenceId": "evidence:evd_hidden",
                "confidence": 0.7,
                "rationale": "Citation must be visible",
            },
        )
    assert exc.value.code == AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE


@pytest.mark.asyncio
async def test_attach_evidence_persists_contradiction_flag() -> None:
    ctx = _ctx(visible={"evidence:evd_visible"})
    result = await handle_attach_evidence(
        ctx,
        {
            "provenance": {
                "sourceType": "existing_evidence",
                "sourceId": "evidence:evd_visible",
                "summary": "Conflicting analyst note",
            },
            "evidenceId": "evidence:evd_visible",
            "isContradiction": True,
            "confidence": 0.55,
            "rationale": "Contradicts primary authentication hypothesis",
        },
    )
    assert "attachmentId" in result
    persisted: EvidenceAttachmentV1 = (
        ctx.uow.investigation.add_evidence_attachment.await_args.args[0]
    )
    assert persisted.is_contradiction is True
    assert persisted.evidence_id == "evidence:evd_visible"


def test_contradictory_attachments_remain_distinct_for_oracle() -> None:
    """Contradictory evidence must not be collapsed or discarded."""
    supporting = make_evidence_attachment(
        attachment_id="eatt_support",
        source_id="evidence:evd_visible",
        is_contradiction=False,
    )
    contradicting = make_evidence_attachment(
        attachment_id="eatt_contra",
        source_id="evidence:evd_visible",
        is_contradiction=True,
        evidence_id="evidence:evd_visible",
    )
    assert supporting.is_contradiction is False
    assert contradicting.is_contradiction is True
    assert supporting.provenance.source_id == contradicting.provenance.source_id
    assert supporting.id != contradicting.id


def test_evidence_attachment_contract_requires_schema_version() -> None:
    with pytest.raises(ContractValidationError):
        EvidenceAttachmentV1(
            schema_version=99,
            id="eatt_invalid",
            incident_id="incident:inc_synthetic_001",
            session_id="agent-session:ags_synthetic_001",
            task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            provenance=make_evidence_attachment(
                attachment_id="eatt_tmp",
                source_id="evidence:evd_visible",
            ).provenance,
            confidence=0.5,
            rationale="invalid schema",
            created_at=datetime(2026, 6, 30, 2, 10, 0, tzinfo=UTC),
        )
    valid = make_evidence_attachment(
        attachment_id="eatt_valid",
        source_id="evidence:evd_visible",
        is_contradiction=True,
    )
    assert valid.schema_version == EVIDENCE_ATTACHMENT_SCHEMA_VERSION
