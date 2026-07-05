"""Hypothesis comparison matrix builder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.hypothesis import (
    HypothesisComparisonEntryV1,
    HypothesisComparisonV1,
    HypothesisRevisionV1,
)
from aegis_contracts.versioning import HYPOTHESIS_COMPARISON_SCHEMA_VERSION

from aegis_agents.runtime.ids import new_runtime_id


def build_hypothesis_comparison(
    *,
    incident_id: str,
    session_id: str,
    task_id: str,
    revisions: list[HypothesisRevisionV1],
    summary: str,
    matrix: dict[str, Any] | None = None,
) -> HypothesisComparisonV1 | None:
    if len(revisions) < 2:
        return None

    entries: list[HypothesisComparisonEntryV1] = []
    for revision in revisions:
        shared: set[str] = set()
        unique = set(revision.supporting_evidence_ids)
        contradicting = set(revision.contradicting_evidence_ids)
        for other in revisions:
            if other.id == revision.id:
                continue
            other_support = set(other.supporting_evidence_ids)
            shared.update(unique & other_support)
            unique -= other_support
        entries.append(
            HypothesisComparisonEntryV1(
                hypothesis_id=revision.hypothesis_id,
                revision_id=revision.id,
                shared_evidence_ids=sorted(shared),
                unique_evidence_ids=sorted(unique),
                contradicting_evidence_ids=sorted(contradicting),
                confidence_point=revision.confidence.point,
            )
        )

    return HypothesisComparisonV1(
        schema_version=HYPOTHESIS_COMPARISON_SCHEMA_VERSION,
        id=new_runtime_id("hcmp"),
        incident_id=incident_id,
        session_id=session_id,
        task_id=task_id,
        entries=entries,
        summary=summary,
        matrix=matrix or {},
        created_at=datetime.now(UTC),
    )
