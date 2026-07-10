"""After-action view model assembly."""

from __future__ import annotations

from aegis_contracts.scoring import (
    AfterActionViewModelV1,
    RunScoreV1,
)
from aegis_contracts.versioning import AFTER_ACTION_VIEW_MODEL_SCHEMA_VERSION

from aegis_scoring.facts import ScoringFacts


def build_after_action_view_model(facts: ScoringFacts, score: RunScoreV1) -> AfterActionViewModelV1:
    bookmarks: list[dict[str, object]] = []
    timeline: list[dict[str, object]] = []

    for component in score.components:
        for explanation in component.explanations:
            if explanation.sequence is not None:
                bookmarks.append(
                    {
                        "label": f"{component.label}: {explanation.rule_id}",
                        "sequence": explanation.sequence,
                        "kind": "detection",
                        "relatedId": explanation.event_ids[0] if explanation.event_ids else None,
                    }
                )
                timeline.append(
                    {
                        "sequence": explanation.sequence,
                        "label": explanation.reason[:200],
                        "kind": "score_explanation",
                        "relatedId": explanation.rule_id,
                    }
                )

    for review in score.decision_reviews:
        bookmarks.append(
            {
                "label": f"Decision: {review.operator_action}",
                "sequence": review.sequence,
                "kind": "decision",
                "relatedId": review.decision_id,
            }
        )
        timeline.append(
            {
                "sequence": review.sequence,
                "label": f"Operator {review.operator_action} ({review.outcome.value})",
                "kind": "decision",
                "relatedId": review.decision_id,
            }
        )

    for missed in score.missed_evidence:
        if missed.bookmark_sequence is not None:
            bookmarks.append(
                {
                    "label": f"Missed evidence: {missed.expected_evidence_key}",
                    "sequence": missed.bookmark_sequence,
                    "kind": "missed_evidence",
                    "relatedId": missed.expected_evidence_key,
                }
            )

    for alt in score.valid_alternatives:
        bookmarks.append(
            {
                "label": f"Alternative: {alt.label}",
                "sequence": score.provenance.input_event_sequence_to,
                "kind": "alternative",
                "relatedId": alt.alternative_id,
            }
        )

    lessons = list(facts.lessons)
    if score.missed_evidence:
        lessons.append("Review missed evidence earlier in the investigation timeline.")
    if score.valid_alternatives:
        lessons.append(
            "Compare labelled counterfactual alternatives with the authoritative run outcome."
        )

    return AfterActionViewModelV1.model_validate(
        {
            "schemaVersion": AFTER_ACTION_VIEW_MODEL_SCHEMA_VERSION,
            "runId": facts.run_id,
            "runStatus": facts.run_status,
            "score": score.model_dump(by_alias=True),
            "affectedAssetIds": facts.affected_asset_ids,
            "lessons": lessons,
            "scribeReportId": facts.scribe_report_id,
            "scribeVersionNumber": facts.scribe_version_number,
            "bookmarks": bookmarks,
            "timelineHighlights": sorted(timeline, key=lambda item: int(item["sequence"])),
        }
    )
