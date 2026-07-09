"""Validate narrative claims and citations against authoritative report sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis_contracts.reports import (
    AfterActionReportSourceV1,
    GroundingValidationResultV1,
    ReportCitationKindV1,
    ReportCitationV1,
    ReportClaimCategoryV1,
    ReportClaimV1,
)
from aegis_contracts.versioning import (
    GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION,
    REPORT_CITATION_SCHEMA_VERSION,
    REPORT_CLAIM_SCHEMA_VERSION,
)

_FACT_CATEGORIES = {
    ReportClaimCategoryV1.OBSERVED_FACT,
    ReportClaimCategoryV1.PERSISTED_EVENT,
    ReportClaimCategoryV1.INVESTIGATION_EVIDENCE,
}


@dataclass
class GroundingBatchResult:
    claims: list[ReportClaimV1] = field(default_factory=list)
    validation_results: list[GroundingValidationResultV1] = field(default_factory=list)
    grounding_failed: bool = False
    rejected_claim_count: int = 0


def _resolve_reference(source: AfterActionReportSourceV1, citation: ReportCitationV1) -> bool:
    reference_id = citation.reference_id
    match citation.kind:
        case ReportCitationKindV1.EVENT:
            return reference_id in source.event_ids
        case ReportCitationKindV1.EVIDENCE:
            return reference_id in source.evidence_ids
        case ReportCitationKindV1.HYPOTHESIS:
            return reference_id in source.hypothesis_ids
        case ReportCitationKindV1.PROPOSAL:
            return reference_id in source.proposal_ids
        case ReportCitationKindV1.POLICY_DECISION:
            return reference_id in source.policy_decision_ids
        case ReportCitationKindV1.ALERT:
            return reference_id in source.alert_ids
        case ReportCitationKindV1.ASSET:
            return reference_id in source.affected_asset_ids
        case ReportCitationKindV1.AGENT_SESSION:
            return reference_id in source.agent_session_ids
        case ReportCitationKindV1.AGENT_TASK | ReportCitationKindV1.MODEL_SCORE:
            return bool(reference_id)
        case _:
            return False


def validate_claim_citations(
    *,
    claim_id: str,
    citations: list[ReportCitationV1],
    source: AfterActionReportSourceV1,
) -> GroundingValidationResultV1:
    citation_results: list[dict[str, Any]] = []
    for citation in citations:
        valid = _resolve_reference(source, citation)
        citation_results.append(
            {
                "referenceId": citation.reference_id,
                "kind": citation.kind.value,
                "valid": valid,
            }
        )
    all_valid = bool(citations) and all(item["valid"] for item in citation_results)
    return GroundingValidationResultV1(
        schema_version=GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION,
        claim_id=claim_id,
        valid=all_valid,
        citation_results=citation_results,
        rejection_reason=None if all_valid else "One or more citations could not be resolved",
    )


def _normalize_category(raw: str) -> ReportClaimCategoryV1:
    try:
        return ReportClaimCategoryV1(raw)
    except ValueError:
        return ReportClaimCategoryV1.UNSUPPORTED


def ground_narrative_claims(
    *,
    structured_claims: list[dict[str, Any]],
    source: AfterActionReportSourceV1,
) -> GroundingBatchResult:
    result = GroundingBatchResult()
    for index, raw in enumerate(structured_claims, start=1):
        claim_id = str(raw.get("claimId") or f"narrative_{index:03d}")
        category = _normalize_category(str(raw.get("category", "agent_inference")))
        citations = [
            ReportCitationV1(
                schema_version=REPORT_CITATION_SCHEMA_VERSION,
                kind=ReportCitationKindV1(item.get("kind", "evidence")),
                reference_id=str(item["referenceId"]),
                label=str(item.get("label", item["referenceId"])),
                sequence=item.get("sequence"),
                rationale=str(item.get("rationale", "")),
            )
            for item in raw.get("citations", [])
            if item.get("referenceId")
        ]
        validation = validate_claim_citations(
            claim_id=claim_id,
            citations=citations,
            source=source,
        )
        result.validation_results.append(validation)

        grounded = validation.valid
        rejection_reason = validation.rejection_reason
        final_category = category
        if category in _FACT_CATEGORIES and not grounded:
            final_category = ReportClaimCategoryV1.UNSUPPORTED
            grounded = False
            rejection_reason = rejection_reason or "Factual claim lacked resolvable citations"
            result.grounding_failed = True
            result.rejected_claim_count += 1
        elif not grounded and category not in {
            ReportClaimCategoryV1.UNSUPPORTED,
            ReportClaimCategoryV1.UNCERTAIN,
            ReportClaimCategoryV1.AGENT_INFERENCE,
        }:
            final_category = ReportClaimCategoryV1.UNCERTAIN
            result.grounding_failed = True

        result.claims.append(
            ReportClaimV1(
                schema_version=REPORT_CLAIM_SCHEMA_VERSION,
                claim_id=claim_id,
                category=final_category,
                text=str(raw.get("text", "")),
                confidence=raw.get("confidence"),
                uncertainty=raw.get("uncertainty"),
                citations=citations if grounded else [],
                grounded=grounded,
                rejection_reason=rejection_reason,
            )
        )
    return result
