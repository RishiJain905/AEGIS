"""Deterministic claim grounding for ORACLE hypotheses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis_contracts.hypothesis import ClaimKindV1, HypothesisClaimV1
from aegis_contracts.investigation import EvidenceAttachmentV1, InvestigationDetailV1
from aegis_contracts.versioning import HYPOTHESIS_CLAIM_SCHEMA_VERSION


@dataclass
class GroundingContext:
    visible_evidence_ids: set[str]
    attachment_by_id: dict[str, EvidenceAttachmentV1]
    attachment_evidence_ids: set[str]


@dataclass
class GroundedClaimResult:
    claims: list[HypothesisClaimV1] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    rejected_claims: list[str] = field(default_factory=list)
    downgraded_claims: list[str] = field(default_factory=list)


def build_grounding_context(
    investigation: InvestigationDetailV1,
    visible_evidence_ids: set[str],
) -> GroundingContext:
    attachment_by_id = {item.id: item for item in investigation.evidence_attachments}
    attachment_evidence_ids = {
        item.evidence_id
        for item in investigation.evidence_attachments
        if item.evidence_id is not None
    }
    return GroundingContext(
        visible_evidence_ids=visible_evidence_ids,
        attachment_by_id=attachment_by_id,
        attachment_evidence_ids=attachment_evidence_ids,
    )


def _resolve_claim_kind(
    raw_kind: str,
    evidence_ids: list[str],
    attachment_ids: list[str],
    context: GroundingContext,
) -> ClaimKindV1:
    if raw_kind == "unsupported_claim":
        return ClaimKindV1.UNSUPPORTED_CLAIM
    if raw_kind in {"observed_fact", "model_score", "graph_risk", "agent_inference"}:
        kind = ClaimKindV1(raw_kind)
    else:
        kind = ClaimKindV1.AGENT_INFERENCE

    for attachment_id in attachment_ids:
        attachment = context.attachment_by_id.get(attachment_id)
        if attachment is None:
            continue
        source_type = attachment.provenance.source_type.value
        if source_type == "risk_path":
            return ClaimKindV1.GRAPH_RISK
        if source_type in {"event", "alert", "asset", "existing_evidence"}:
            return ClaimKindV1.OBSERVED_FACT

    if evidence_ids and all(item in context.visible_evidence_ids for item in evidence_ids):
        return ClaimKindV1.OBSERVED_FACT
    return kind


def ground_hypothesis_claims(
    *,
    structured_claims: list[dict[str, Any]],
    supporting_evidence_ids: list[str],
    contradicting_evidence_ids: list[str],
    context: GroundingContext,
) -> GroundedClaimResult:
    result = GroundedClaimResult()
    seen_supporting = set(supporting_evidence_ids)
    seen_contradicting = set(contradicting_evidence_ids)

    for raw in structured_claims:
        evidence_ids = [item for item in raw.get("evidenceIds", []) if item]
        attachment_ids = [item for item in raw.get("attachmentIds", []) if item]
        kind = _resolve_claim_kind(
            raw.get("kind", "agent_inference"),
            evidence_ids,
            attachment_ids,
            context,
        )

        grounded_evidence = [
            item for item in evidence_ids if item in context.visible_evidence_ids
        ]
        grounded_attachments = [
            item for item in attachment_ids if item in context.attachment_by_id
        ]
        has_grounding = bool(grounded_evidence or grounded_attachments)

        if kind == ClaimKindV1.UNSUPPORTED_CLAIM or (
            kind == ClaimKindV1.OBSERVED_FACT and not has_grounding
        ):
            if raw.get("isAssumption"):
                kind = ClaimKindV1.AGENT_INFERENCE
                result.downgraded_claims.append(raw["text"])
            else:
                result.rejected_claims.append(raw["text"])
                result.claims.append(
                    HypothesisClaimV1(
                        schema_version=HYPOTHESIS_CLAIM_SCHEMA_VERSION,
                        kind=ClaimKindV1.UNSUPPORTED_CLAIM,
                        text=raw["text"],
                        evidence_ids=[],
                        attachment_ids=[],
                        is_assumption=False,
                    )
                )
                continue

        if not has_grounding and kind != ClaimKindV1.AGENT_INFERENCE:
            kind = ClaimKindV1.AGENT_INFERENCE
            result.downgraded_claims.append(raw["text"])

        for evidence_id in grounded_evidence:
            attachment = next(
                (
                    item
                    for item in context.attachment_by_id.values()
                    if item.evidence_id == evidence_id and item.is_contradiction
                ),
                None,
            )
            if attachment is not None:
                seen_contradicting.add(evidence_id)
            else:
                seen_supporting.add(evidence_id)

        result.claims.append(
            HypothesisClaimV1(
                schema_version=HYPOTHESIS_CLAIM_SCHEMA_VERSION,
                kind=kind,
                text=raw["text"],
                evidence_ids=grounded_evidence,
                attachment_ids=grounded_attachments,
                is_assumption=bool(raw.get("isAssumption", False))
                or kind == ClaimKindV1.AGENT_INFERENCE,
            )
        )

    for evidence_id in supporting_evidence_ids:
        if evidence_id not in context.visible_evidence_ids:
            continue
        attachment = next(
            (
                item
                for item in context.attachment_by_id.values()
                if item.evidence_id == evidence_id and item.is_contradiction
            ),
            None,
        )
        if attachment is not None:
            seen_contradicting.add(evidence_id)
        else:
            seen_supporting.add(evidence_id)
    for evidence_id in contradicting_evidence_ids:
        if evidence_id in context.visible_evidence_ids:
            seen_contradicting.add(evidence_id)

    result.supporting_evidence_ids = sorted(seen_supporting)
    result.contradicting_evidence_ids = sorted(seen_contradicting)
    return result
