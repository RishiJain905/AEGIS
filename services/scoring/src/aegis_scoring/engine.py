"""Deterministic scoring engine — pure function over ScoringFacts."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.scoring import (
    GRADING_ENGINE_VERSION,
    MissedEvidenceItemV1,
    RunScoreV1,
    ScoreErrorCode,
)
from aegis_contracts.versioning import (
    MISSED_EVIDENCE_ITEM_SCHEMA_VERSION,
    RUN_SCORE_SCHEMA_VERSION,
    SCORE_PROVENANCE_SCHEMA_VERSION,
)

from aegis_scoring.alternatives import build_valid_alternatives
from aegis_scoring.checksums import hash_payload
from aegis_scoring.criteria import (
    CRITERION_HANDLERS,
    PASSING_SCORE_THRESHOLD,
    grade_for_score,
    score_evidence_coverage,
)
from aegis_scoring.decisions import build_decision_reviews
from aegis_scoring.errors import ScoringError
from aegis_scoring.facts import ScoringFacts
from aegis_scoring.ids import new_runtime_id

COMPLETED_STATUSES = frozenset({"completed", "complete", "finished", "ended"})


def _input_checksum(facts: ScoringFacts) -> str:
    payload = {
        "runId": facts.run_id,
        "scenarioId": facts.scenario_id,
        "scenarioVersion": facts.scenario_version,
        "rubricVersion": facts.rubric.rubric_version,
        "gradingEngineVersion": GRADING_ENGINE_VERSION,
        "events": [
            {
                "eventId": e.event_id,
                "sequence": e.sequence,
                "eventType": e.event_type,
                "assetId": e.asset_id,
            }
            for e in sorted(facts.events, key=lambda x: x.sequence)
        ],
        "evidence": [
            {"evidenceId": e.evidence_id, "sourceEventId": e.source_event_id, "assetId": e.asset_id}
            for e in facts.evidence
        ],
        "hypotheses": [
            {"hypothesisId": h.hypothesis_id, "statement": h.statement, "confidence": h.confidence}
            for h in facts.hypotheses
        ],
        "approvals": [
            {
                "approvalId": a.approval_id,
                "proposalId": a.proposal_id,
                "decision": a.decision,
                "sequence": a.sequence,
            }
            for a in facts.approvals
        ],
        "executedActions": [
            {
                "actionId": a.action_id,
                "proposalId": a.proposal_id,
                "outcome": a.outcome,
                "impactScore": a.impact_score,
            }
            for a in facts.executed_actions
        ],
        "trueCauseId": facts.true_cause_id,
        "selectedResponseBranch": facts.selected_response_branch,
    }
    return hash_payload(payload)


def compute_run_score(
    facts: ScoringFacts,
    *,
    score_id: str | None = None,
    calculated_at: str | None = None,
) -> RunScoreV1:
    if facts.run_status.lower() not in COMPLETED_STATUSES:
        raise ScoringError(
            code=ScoreErrorCode.SCORE_INCOMPLETE_RUN,
            message=f"Run {facts.run_id} is not completed (status={facts.run_status}).",
            details={"runId": facts.run_id, "status": facts.run_status},
        )

    if not facts.rubric.criteria:
        raise ScoringError(
            code=ScoreErrorCode.SCORE_RUBRIC_MISSING,
            message="Scoring rubric has no criteria.",
        )

    if (
        facts.rubric.grading_engine_version != GRADING_ENGINE_VERSION
        and facts.rubric.grading_engine_version
        not in {
            GRADING_ENGINE_VERSION,
            "1.0.0-phase29",
        }
    ):
        raise ScoringError(
            code=ScoreErrorCode.SCORE_RUBRIC_INCOMPATIBLE,
            message=(
                f"Rubric grading engine {facts.rubric.grading_engine_version} "
                f"incompatible with {GRADING_ENGINE_VERSION}."
            ),
        )

    max_score = facts.rubric.max_score
    components = []
    missed_raw: list[dict[str, object]] = []

    for criterion in facts.rubric.criteria:
        cid = criterion.id
        if cid == "criterion-evidence-coverage":
            component, missed_raw = score_evidence_coverage(
                facts, criterion.weight, criterion.label, max_score
            )
            components.append(component)
            continue
        handler = CRITERION_HANDLERS.get(cid)
        if handler is None:
            raise ScoringError(
                code=ScoreErrorCode.SCORE_VALIDATION_FAILED,
                message=f"Unknown criterion id: {cid}",
                details={"criterionId": cid},
            )
        components.append(handler(facts, criterion.weight, criterion.label, max_score))

    overall = round(sum(c.weighted_contribution for c in components), 4)
    overall = max(0.0, min(max_score, overall))

    decision_reviews = build_decision_reviews(facts)
    # Apply small decision deltas without exceeding max
    decision_adjustment = sum(d.score_delta for d in decision_reviews) * max_score
    # Cap decision adjustment to ±5 points
    decision_adjustment = max(-5.0, min(5.0, decision_adjustment))
    overall = round(max(0.0, min(max_score, overall + decision_adjustment)), 4)

    alternatives = build_valid_alternatives(facts, authoritative_overall=overall)

    sequences = [e.sequence for e in facts.events]
    seq_from = min(sequences) if sequences else 0
    seq_to = max(sequences) if sequences else 0
    input_checksum = _input_checksum(facts)
    calculated = (
        calculated_at
        or facts.calculated_at
        or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )
    score_id_value = score_id or new_runtime_id("scr")

    fingerprint = hash_payload(
        {
            "scenarioVersion": facts.scenario_version,
            "rubricVersion": facts.rubric.rubric_version,
            "gradingEngineVersion": GRADING_ENGINE_VERSION,
            "runId": facts.run_id,
            "eventSeqFrom": seq_from,
            "eventSeqTo": seq_to,
            "inputChecksum": input_checksum,
        }
    )

    integrity_payload = {
        "scoreId": score_id_value,
        "overallScore": overall,
        "components": [c.model_dump(by_alias=True) for c in components],
        "fingerprint": fingerprint,
        "inputChecksum": input_checksum,
    }
    integrity_checksum = hash_payload(integrity_payload)

    missed_evidence = [
        MissedEvidenceItemV1.model_validate(
            {
                "schemaVersion": MISSED_EVIDENCE_ITEM_SCHEMA_VERSION,
                **item,
            }
        )
        for item in missed_raw
        if not item.get("discovered")
    ]

    coaching = None
    if missed_evidence:
        coaching = (
            "Non-authoritative coaching: review missed evidence items earlier and "
            "compare agent recommendations with operator decisions in the timeline."
        )

    return RunScoreV1.model_validate(
        {
            "schemaVersion": RUN_SCORE_SCHEMA_VERSION,
            "scoreId": score_id_value,
            "runId": facts.run_id,
            "incidentId": facts.incident_id,
            "overallScore": overall,
            "maxScore": max_score,
            "grade": grade_for_score(overall),
            "passed": overall >= PASSING_SCORE_THRESHOLD,
            "components": [c.model_dump(by_alias=True) for c in components],
            "provenance": {
                "schemaVersion": SCORE_PROVENANCE_SCHEMA_VERSION,
                "runId": facts.run_id,
                "scenarioId": facts.scenario_id,
                "scenarioVersion": facts.scenario_version,
                "rubricVersion": facts.rubric.rubric_version,
                "gradingEngineVersion": GRADING_ENGINE_VERSION,
                "inputEventSequenceFrom": seq_from,
                "inputEventSequenceTo": seq_to,
                "inputChecksum": input_checksum,
                "integrityChecksum": integrity_checksum,
                "calculatedAt": calculated,
                "fingerprint": fingerprint,
            },
            "decisionReviews": [d.model_dump(by_alias=True) for d in decision_reviews],
            "missedEvidence": [m.model_dump(by_alias=True) for m in missed_evidence],
            "validAlternatives": [a.model_dump(by_alias=True) for a in alternatives],
            "coachingText": coaching,
            "coachingAuthoritative": False,
            "hiddenCauseId": facts.true_cause_id,
            "hiddenCauseLabel": facts.true_cause_label,
            "hiddenCauseRevealed": True,
        }
    )
