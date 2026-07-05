"""ORACLE grounding tests."""

from __future__ import annotations

from aegis_agents.roles.oracle.grounding import (
    GroundingContext,
    build_grounding_context,
    ground_hypothesis_claims,
)
from aegis_contracts.hypothesis import ClaimKindV1
from aegis_contracts.investigation import InvestigationDetailV1


def test_unsupported_claim_is_marked_when_not_assumption() -> None:
    context = GroundingContext(
        visible_evidence_ids={"evidence:evd_001"},
        attachment_by_id={},
        attachment_evidence_ids=set(),
    )
    result = ground_hypothesis_claims(
        structured_claims=[
            {
                "kind": "observed_fact",
                "text": "Unverified lateral movement to finance subnet",
                "evidenceIds": ["evidence:evd_missing"],
            }
        ],
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
        context=context,
    )
    assert result.rejected_claims
    assert result.claims[0].kind == ClaimKindV1.UNSUPPORTED_CLAIM


def test_inference_downgraded_when_marked_assumption() -> None:
    context = GroundingContext(
        visible_evidence_ids=set(),
        attachment_by_id={},
        attachment_evidence_ids=set(),
    )
    result = ground_hypothesis_claims(
        structured_claims=[
            {
                "kind": "observed_fact",
                "text": "Possible maintenance overlap",
                "evidenceIds": [],
                "isAssumption": True,
            }
        ],
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
        context=context,
    )
    assert result.downgraded_claims
    assert result.claims[0].kind == ClaimKindV1.AGENT_INFERENCE
    assert result.claims[0].is_assumption is True


def test_contradictory_attachment_preserves_contradiction_ids() -> None:
    from datetime import UTC, datetime

    from aegis_contracts.investigation import (
        EvidenceAttachmentV1,
        EvidenceProvenanceV1,
        EvidenceSourceType,
    )
    from aegis_contracts.versioning import EVIDENCE_ATTACHMENT_SCHEMA_VERSION

    attachment = EvidenceAttachmentV1(
        schema_version=EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
        id="eatt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        incident_id="incident:watchtower-trace-integration",
        session_id="agent-session:ags_watchtower_trace",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provenance=EvidenceProvenanceV1(
            source_type=EvidenceSourceType.ALERT,
            source_id="alert:alt_watchtower_trace_001",
            summary="Contradictory timing",
        ),
        evidence_id="evidence:evd_watchtower_trace_001",
        is_contradiction=True,
        confidence=0.7,
        rationale="Contradicts primary hypothesis",
        created_at=datetime.now(UTC),
    )
    investigation = InvestigationDetailV1(
        schema_version=2,
        incident_id="incident:watchtower-trace-integration",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        evidence_attachments=[attachment],
    )
    context = build_grounding_context(investigation, {"evidence:evd_watchtower_trace_001"})
    result = ground_hypothesis_claims(
        structured_claims=[],
        supporting_evidence_ids=["evidence:evd_watchtower_trace_001"],
        contradicting_evidence_ids=[],
        context=context,
    )
    assert "evidence:evd_watchtower_trace_001" in result.contradicting_evidence_ids
