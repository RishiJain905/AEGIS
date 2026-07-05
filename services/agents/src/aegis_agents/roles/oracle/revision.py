"""Append-only hypothesis revision helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import HypothesisV1
from aegis_contracts.hypothesis import (
    ContradictionLinkV1,
    HypothesisFamilyV1,
    HypothesisRevisionV1,
    HypothesisStatusV1,
)
from aegis_contracts.versioning import (
    CONTRADICTION_LINK_SCHEMA_VERSION,
    HYPOTHESIS_REVISION_SCHEMA_VERSION,
    HYPOTHESIS_SCHEMA_VERSION,
)

from aegis_agents.roles.oracle.confidence import (
    build_confidence_assessment,
    validate_confidence_bounds,
)
from aegis_agents.roles.oracle.grounding import GroundedClaimResult
from aegis_agents.runtime.ids import new_runtime_id


def build_initial_hypothesis(
    *,
    incident_id: str,
    family: HypothesisFamilyV1,
    revision_id: str,
    created_at: datetime | None = None,
) -> HypothesisV1:
    now = created_at or datetime.now(UTC)
    return HypothesisV1(
        schema_version=HYPOTHESIS_SCHEMA_VERSION,
        id=new_runtime_id("hyp"),
        incident_id=incident_id,
        current_revision_id=revision_id,
        family=family.value,
        status=HypothesisStatusV1.ACTIVE.value,
        created_at=now,
    )


def build_revision(
    *,
    hypothesis_id: str,
    incident_id: str,
    session_id: str,
    task_id: str,
    revision_number: int,
    structured: dict[str, Any],
    grounded: GroundedClaimResult,
    status: HypothesisStatusV1 = HypothesisStatusV1.ACTIVE,
) -> HypothesisRevisionV1:
    confidence = build_confidence_assessment(
        structured["confidence"],
        supporting_count=len(grounded.supporting_evidence_ids),
        contradicting_count=len(grounded.contradicting_evidence_ids),
        total_visible=len(grounded.supporting_evidence_ids)
        + len(grounded.contradicting_evidence_ids),
    )
    validate_confidence_bounds(confidence)

    contradiction_links = [
        ContradictionLinkV1(
            schema_version=CONTRADICTION_LINK_SCHEMA_VERSION,
            supporting_evidence_ids=item.get("supportingEvidenceIds", []),
            contradicting_evidence_ids=item.get("contradictingEvidenceIds", []),
            supporting_attachment_ids=item.get("supportingAttachmentIds", []),
            contradicting_attachment_ids=item.get("contradictingAttachmentIds", []),
            rationale=item["rationale"],
        )
        for item in structured.get("contradictionLinks", [])
    ]

    return HypothesisRevisionV1(
        schema_version=HYPOTHESIS_REVISION_SCHEMA_VERSION,
        id=new_runtime_id("hrev"),
        hypothesis_id=hypothesis_id,
        incident_id=incident_id,
        session_id=session_id,
        task_id=task_id,
        revision_number=revision_number,
        claim=structured["claim"],
        family=HypothesisFamilyV1(structured["family"]),
        confidence=confidence,
        claims=grounded.claims,
        assumptions=structured.get("assumptions", []),
        supporting_evidence_ids=grounded.supporting_evidence_ids,
        contradicting_evidence_ids=grounded.contradicting_evidence_ids,
        unknowns=structured.get("unknowns", []),
        predictions=structured.get("predictions", []),
        contradiction_links=contradiction_links,
        status=status,
        rationale=structured.get("rationale", structured["claim"]),
        created_at=datetime.now(UTC),
    )
