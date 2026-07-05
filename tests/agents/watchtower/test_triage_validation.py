"""WatchtowerTriageResult validation and idempotency tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.watchtower.handler import WatchtowerRoleHandler
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.investigation import (
    TriageEscalationLevel,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION
from pydantic import ValidationError


def _valid_triage(**overrides: object) -> WatchtowerTriageResultV1:
    base = WatchtowerTriageResultV1(
        schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
        id="wtri_test_001",
        incident_id="incident:inc_synthetic_001",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        session_id="agent-session:ags_synthetic_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        escalation=TriageEscalationLevel.INVESTIGATE,
        escalation_rationale="Investigation recommended based on correlated alerts.",
        confidence=0.75,
        idempotency_key="triage-test-001",
        created_at=datetime(2026, 6, 30, 2, 5, 0, tzinfo=UTC),
    )
    return base.model_copy(update=overrides)


def test_valid_triage_result_parses() -> None:
    triage = _valid_triage()
    assert triage.escalation == TriageEscalationLevel.INVESTIGATE
    assert triage.schema_version == WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION


def test_unsupported_schema_version_rejected() -> None:
    with pytest.raises(ContractValidationError) as exc:
        WatchtowerTriageResultV1(
            schema_version=99,
            id="wtri_test_001",
            incident_id="incident:inc_synthetic_001",
            run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            session_id="agent-session:ags_synthetic_001",
            task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            escalation=TriageEscalationLevel.INVESTIGATE,
            escalation_rationale="Investigation recommended based on correlated alerts.",
            confidence=0.75,
            idempotency_key="triage-test-001",
            created_at=datetime(2026, 6, 30, 2, 5, 0, tzinfo=UTC),
        )
    assert exc.value.code == ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED


def test_confidence_must_be_bounded() -> None:
    with pytest.raises(ValidationError):
        WatchtowerTriageResultV1(
            schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
            id="wtri_test_001",
            incident_id="incident:inc_synthetic_001",
            run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            session_id="agent-session:ags_synthetic_001",
            task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            escalation=TriageEscalationLevel.INVESTIGATE,
            escalation_rationale="Investigation recommended based on correlated alerts.",
            confidence=1.5,
            idempotency_key="triage-test-001",
            created_at=datetime(2026, 6, 30, 2, 5, 0, tzinfo=UTC),
        )


def test_idempotency_key_is_required() -> None:
    with pytest.raises(ValidationError):
        WatchtowerTriageResultV1(
            schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
            id="wtri_test_001",
            incident_id="incident:inc_synthetic_001",
            run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            session_id="agent-session:ags_synthetic_001",
            task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            escalation=TriageEscalationLevel.INVESTIGATE,
            escalation_rationale="Investigation recommended based on correlated alerts.",
            confidence=0.75,
            idempotency_key="",
            created_at=datetime(2026, 6, 30, 2, 5, 0, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_handler_skips_persist_when_idempotency_match_exists() -> None:
    handler = WatchtowerRoleHandler()
    existing = _valid_triage()
    uow = AsyncMock()
    uow.investigation.get_triage_by_idempotency = AsyncMock(return_value=existing)
    uow.investigation.add_triage = AsyncMock()
    uow.events.next_sequence = AsyncMock()
    uow.append_event = AsyncMock()

    ctx = PostProcessContext(
        uow=uow,
        session_id=existing.session_id,
        task_id=existing.task_id,
        incident_id=existing.incident_id,
        run_id=existing.run_id,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        idempotency_key=existing.idempotency_key,
    )
    await handler.post_process(
        ctx=ctx,
        structured={
            "alertSummaries": [],
            "groupedAlertIds": [],
            "separatedAlertIds": [],
            "correlationDecisions": [],
            "escalation": "investigate",
            "escalationRationale": "Should not persist",
            "confidence": 0.5,
            "evidenceCitations": [],
            "toolRequests": [],
        },
    )

    uow.investigation.add_triage.assert_not_called()
    uow.append_event.assert_not_called()
