"""Historical-time operator decision reviews."""

from __future__ import annotations

from aegis_contracts.scoring import (
    DecisionReviewV1,
)
from aegis_contracts.versioning import (
    DECISION_REVIEW_SCHEMA_VERSION,
    SCORE_EXPLANATION_SCHEMA_VERSION,
)

from aegis_scoring.facts import ScoringFacts


def build_decision_reviews(facts: ScoringFacts) -> list[DecisionReviewV1]:
    reviews: list[DecisionReviewV1] = []
    for approval in facts.approvals:
        available_events = [e for e in facts.events if e.sequence <= approval.sequence]
        available_evidence = [
            ev
            for ev in facts.evidence
            if ev.created_sequence is None or ev.created_sequence <= approval.sequence
        ]
        proposal = next((p for p in facts.proposals if p.proposal_id == approval.proposal_id), None)
        agent_rec = proposal.summary if proposal else None
        policy = proposal.policy_decision if proposal else None

        outcome = "neutral"
        score_delta = 0.0
        rule_id = "rule-decision-historical-evaluation"
        reason = f"Operator {approval.decision} proposal {approval.proposal_id}."

        if approval.decision == "approved":
            if policy in {None, "allow", "require_approval", "approved"}:
                outcome = "credited"
                score_delta = 0.05
                rule_id = "rule-decision-proportionate-approval"
                reason = (
                    "Operator approved a proposal using only information "
                    "available at decision time."
                )
            elif policy in {"deny", "rejected"}:
                outcome = "penalized"
                score_delta = -0.1
                rule_id = "rule-decision-unsafe-approval"
                reason = "Operator approved a proposal despite a denying policy decision."
        elif approval.decision == "rejected":
            if policy in {"deny", "rejected"}:
                outcome = "restraint_credited"
                score_delta = 0.08
                rule_id = "rule-decision-correct-rejection"
                reason = "Operator correctly rejected an unsafe or denied proposal."
            else:
                outcome = "neutral"
                score_delta = 0.0
                reason = "Operator rejected a proposal; recorded without future-knowledge bias."
        elif approval.decision == "modified":
            outcome = "credited"
            score_delta = 0.04
            rule_id = "rule-decision-modification"
            reason = "Operator modified a proposal before execution."

        reviews.append(
            DecisionReviewV1.model_validate(
                {
                    "schemaVersion": DECISION_REVIEW_SCHEMA_VERSION,
                    "decisionId": approval.approval_id,
                    "kind": {
                        "approved": "approval",
                        "rejected": "rejection",
                        "modified": "modification",
                        "cancelled": "cancellation",
                    }.get(approval.decision, "approval"),
                    "sequence": approval.sequence,
                    "proposalId": approval.proposal_id,
                    "operatorAction": approval.decision,
                    "agentRecommendation": agent_rec,
                    "availableInfoSummary": (
                        f"{len(available_events)} events and {len(available_evidence)} evidence "
                        f"items were available at sequence {approval.sequence}."
                    ),
                    "availableEventIds": [e.event_id for e in available_events[-8:]],
                    "availableEvidenceIds": [e.evidence_id for e in available_evidence[-8:]],
                    "outcome": outcome,
                    "scoreDelta": score_delta,
                    "ruleIds": [rule_id],
                    "explanations": [
                        {
                            "schemaVersion": SCORE_EXPLANATION_SCHEMA_VERSION,
                            "ruleId": rule_id,
                            "reason": reason,
                            "eventIds": [e.event_id for e in available_events[-4:]],
                            "evidenceIds": [e.evidence_id for e in available_evidence[-4:]],
                            "decisionIds": [approval.approval_id],
                            "hypothesisIds": [],
                            "proposalIds": [approval.proposal_id],
                            "sequence": approval.sequence,
                        }
                    ],
                    "usedFutureKnowledge": False,
                }
            )
        )
    return reviews
