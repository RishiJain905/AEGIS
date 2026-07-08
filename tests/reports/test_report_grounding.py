"""Unit tests for report grounding validation."""

from __future__ import annotations

from aegis_contracts.reports import (
    AfterActionReportSourceV1,
    ReportCitationKindV1,
    ReportCitationV1,
    ReportClaimCategoryV1,
)
from aegis_contracts.versioning import (
    AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
    REPORT_CITATION_SCHEMA_VERSION,
)
from aegis_reports.grounding import ground_narrative_claims, validate_claim_citations


def _source() -> AfterActionReportSourceV1:
    return AfterActionReportSourceV1(
        schema_version=AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        incident_id="incident:inc_001",
        source_sequence_from=1,
        source_sequence_to=10,
        event_ids=["evt_01ARZ3NDEKTSV4RRFFQ69G5FAW"],
        evidence_ids=["evidence:evt_auth_fail_001"],
        hypothesis_ids=["hyp_01ARZ3NDEKTSV4RRFFQ69G5FBW"],
        proposal_ids=["prp_01ARZ3NDEKTSV4RRFFQ69G5FB9"],
        policy_decision_ids=["pdc_01ARZ3NDEKTSV4RRFFQ69G5FBA"],
    )


def test_valid_citations_pass_grounding() -> None:
    result = ground_narrative_claims(
        structured_claims=[
            {
                "claimId": "claim_001",
                "category": "investigation_evidence",
                "text": "Grounded evidence claim",
                "citations": [
                    {
                        "kind": "evidence",
                        "referenceId": "evidence:evt_auth_fail_001",
                        "label": "Auth failure",
                    }
                ],
            }
        ],
        source=_source(),
    )
    assert result.grounding_failed is False
    assert result.claims[0].grounded is True


def test_hallucinated_fact_claim_rejected_safely() -> None:
    result = ground_narrative_claims(
        structured_claims=[
            {
                "claimId": "claim_bad",
                "category": "observed_fact",
                "text": "Hallucinated fact",
                "citations": [
                    {
                        "kind": "evidence",
                        "referenceId": "evidence:evt_does_not_exist",
                        "label": "Missing",
                    }
                ],
            }
        ],
        source=_source(),
    )
    assert result.grounding_failed is True
    assert result.claims[0].category == ReportClaimCategoryV1.UNSUPPORTED
    assert result.claims[0].grounded is False


def test_validate_claim_citations_detects_invalid_reference() -> None:
    validation = validate_claim_citations(
        claim_id="claim_x",
        citations=[
            ReportCitationV1(
                schema_version=REPORT_CITATION_SCHEMA_VERSION,
                kind=ReportCitationKindV1.HYPOTHESIS,
                reference_id="hyp_missing",
                label="missing",
            )
        ],
        source=_source(),
    )
    assert validation.valid is False
