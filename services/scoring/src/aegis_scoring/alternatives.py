"""Valid alternatives and counterfactual projections (non-authoritative)."""

from __future__ import annotations

from aegis_contracts.scoring import (
    ValidAlternativeV1,
)
from aegis_contracts.versioning import (
    SCORE_EXPLANATION_SCHEMA_VERSION,
    VALID_ALTERNATIVE_SCHEMA_VERSION,
)

from aegis_scoring.facts import ScoringFacts

# Evidence-grounded alternatives per cause — multiple may score well.
_CAUSE_ALTERNATIVES: dict[str, list[tuple[str, str, float]]] = {
    "hidden-cause-compromised-credentials": [
        ("branch-response-contain", "Contain compromised identity path quickly", 2.0),
        ("branch-response-remediate", "Rotate credentials and remediate root access", 3.5),
        ("branch-response-investigate", "Investigate lateral auth before containment", 1.5),
    ],
    "hidden-cause-undocumented-maintenance": [
        ("branch-response-investigate", "Investigate off-window maintenance first", 4.0),
        ("branch-response-remediate", "Remediate defective maintenance change", 3.0),
        ("branch-response-contain", "Contain affected communications path", 0.5),
    ],
    "hidden-cause-defective-deployment": [
        ("branch-response-remediate", "Roll back defective deployment", 4.5),
        ("branch-response-investigate", "Investigate deployment health before rollback", 3.0),
        ("branch-response-contain", "Contain logistics API blast radius", 1.0),
    ],
    "hidden-cause-internal-misuse": [
        ("branch-response-contain", "Contain jumphost exfiltration path", 4.0),
        (
            "branch-response-investigate",
            "Investigate privileged misuse with evidence retention",
            3.5,
        ),
        ("branch-response-remediate", "Revoke misuse privileges and remediate access", 2.5),
    ],
}


def build_valid_alternatives(
    facts: ScoringFacts,
    *,
    authoritative_overall: float,
) -> list[ValidAlternativeV1]:
    cause = facts.true_cause_id
    if not cause:
        return []

    selected = facts.selected_response_branch
    alternatives: list[ValidAlternativeV1] = []
    for branch_id, label, delta in _CAUSE_ALTERNATIVES.get(cause, []):
        if selected and branch_id == selected:
            continue
        projected = round(min(facts.rubric.max_score, authoritative_overall + delta), 4)
        alternatives.append(
            ValidAlternativeV1.model_validate(
                {
                    "schemaVersion": VALID_ALTERNATIVE_SCHEMA_VERSION,
                    "alternativeId": f"alt_{branch_id}",
                    "kind": "valid_response_branch",
                    "authoritative": False,
                    "label": label,
                    "description": (
                        f"Counterfactual alternative: selecting {branch_id} is an "
                        f"evidence-grounded valid response for {cause}. "
                        "This is not a fact from the completed run."
                    ),
                    "projectedOverallScore": projected,
                    "scoreDelta": delta,
                    "ruleIds": [f"rule-cf-response-branch-{branch_id}"],
                    "explanations": [
                        {
                            "schemaVersion": SCORE_EXPLANATION_SCHEMA_VERSION,
                            "ruleId": f"rule-cf-response-branch-{branch_id}",
                            "reason": (
                                f"Projected score delta +{delta} for alternative branch "
                                f"{branch_id}; labelled non-authoritative."
                            ),
                            "eventIds": [],
                            "evidenceIds": [],
                            "decisionIds": [],
                            "hypothesisIds": [],
                            "proposalIds": [],
                            "sequence": None,
                        }
                    ],
                }
            )
        )
    return alternatives
