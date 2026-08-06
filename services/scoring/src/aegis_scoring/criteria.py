"""Deterministic criterion calculators for Phase 29 scoring."""

from __future__ import annotations

from aegis_contracts.scoring import (
    ScoreComponentV1,
    ScoreExplanationV1,
)
from aegis_contracts.versioning import (
    SCORE_COMPONENT_SCHEMA_VERSION,
    SCORE_EXPLANATION_SCHEMA_VERSION,
)

from aegis_scoring.facts import ExpectedEvidenceFact, ScoringFacts

PASSING_SCORE_THRESHOLD = 60.0

GRADE_BANDS: list[tuple[float, str]] = [
    (90.0, "A"),
    (80.0, "B"),
    (70.0, "C"),
    (60.0, "D"),
    (0.0, "F"),
]


def grade_for_score(overall: float) -> str:
    for threshold, band in GRADE_BANDS:
        if overall >= threshold:
            return band
    return "F"


def _explanation(
    rule_id: str,
    reason: str,
    *,
    event_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    decision_ids: list[str] | None = None,
    hypothesis_ids: list[str] | None = None,
    proposal_ids: list[str] | None = None,
    sequence: int | None = None,
) -> ScoreExplanationV1:
    return ScoreExplanationV1.model_validate(
        {
            "schemaVersion": SCORE_EXPLANATION_SCHEMA_VERSION,
            "ruleId": rule_id,
            "reason": reason,
            "eventIds": event_ids or [],
            "evidenceIds": evidence_ids or [],
            "decisionIds": decision_ids or [],
            "hypothesisIds": hypothesis_ids or [],
            "proposalIds": proposal_ids or [],
            "sequence": sequence,
        }
    )


def _component(
    criterion_id: str,
    label: str,
    weight: float,
    raw_score: float,
    max_score: float,
    rule_ids: list[str],
    explanations: list[ScoreExplanationV1],
) -> ScoreComponentV1:
    clamped = max(0.0, min(1.0, raw_score))
    return ScoreComponentV1.model_validate(
        {
            "schemaVersion": SCORE_COMPONENT_SCHEMA_VERSION,
            "criterionId": criterion_id,
            "label": label,
            "weight": weight,
            "rawScore": clamped,
            "weightedContribution": round(clamped * weight * max_score, 4),
            "ruleIds": rule_ids,
            "explanations": [e.model_dump(by_alias=True) for e in explanations],
        }
    )


def _true_cause_expected(facts: ScoringFacts) -> list[ExpectedEvidenceFact]:
    if not facts.true_cause_id:
        return []
    return [e for e in facts.expected_evidence if e.cause_id == facts.true_cause_id]


def _evidence_discovered(
    facts: ScoringFacts, expected: ExpectedEvidenceFact
) -> tuple[bool, list[str], list[str], int | None]:
    matching_events = [
        e
        for e in facts.events
        if e.event_type == expected.event_type
        and (expected.asset_id is None or e.asset_id == expected.asset_id)
    ]
    event_ids = [e.event_id for e in matching_events]
    evidence_ids: list[str] = []
    bookmark: int | None = matching_events[0].sequence if matching_events else None
    for ev in facts.evidence:
        if ev.source_event_id and ev.source_event_id in event_ids or (
            expected.asset_id
            and ev.asset_id == expected.asset_id
            and (
                expected.event_type.split(".")[-1] in ev.summary.lower()
                or expected.asset_id in (ev.summary or "")
                or expected.event_type in (ev.summary or "")
            )
        ):
            evidence_ids.append(ev.evidence_id)
    # Discovered if matching telemetry existed and was attached as evidence, OR
    # matching events exist and evidence references the same asset.
    discovered = bool(evidence_ids) or (
        bool(matching_events)
        and any(
            (ev.asset_id == expected.asset_id and expected.asset_id is not None)
            or (ev.source_event_id in event_ids)
            for ev in facts.evidence
        )
    )
    # Also count as discovered when evidence summary mentions the asset and event pattern
    # was present in the run (operator reviewed the chain).
    if not discovered and matching_events and facts.evidence:
        asset_evidence = [ev for ev in facts.evidence if ev.asset_id == expected.asset_id]
        if asset_evidence:
            discovered = True
            evidence_ids = [ev.evidence_id for ev in asset_evidence]
    return discovered, event_ids, evidence_ids, bookmark


def score_detection_speed(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-detection-speed-window"
    expected = _true_cause_expected(facts)
    if not expected:
        return _component(
            "criterion-detection-speed",
            label,
            weight,
            0.0,
            max_score,
            [rule_id],
            [
                _explanation(
                    rule_id, "No true-cause expected evidence available for detection timing."
                )
            ],
        )

    first_signal_seq: int | None = None
    first_signal_event: str | None = None
    for item in expected:
        for event in facts.events:
            if event.event_type == item.event_type and (
                item.asset_id is None or event.asset_id == item.asset_id
            ):
                if first_signal_seq is None or event.sequence < first_signal_seq:
                    first_signal_seq = event.sequence
                    first_signal_event = event.event_id
                break

    alert_events = [
        e
        for e in facts.events
        if e.event_type.startswith("alert.")
        or e.event_type in {"detection.alert.created", "alert.created"}
    ]
    # Detection proxy from later true-cause signals when formal alerts are absent
    first_alert_seq: int | None = None
    first_alert_id: str | None = None
    for alert in alert_events:
        if (
            first_signal_seq is not None
            and alert.sequence >= first_signal_seq
            and (first_alert_seq is None or alert.sequence < first_alert_seq)
        ):
            first_alert_seq = alert.sequence
            first_alert_id = alert.event_id

    if first_signal_seq is None:
        raw = 0.0
        reason = "True-cause supporting signals were never observed in the run."
        event_ids: list[str] = []
        seq = None
    elif first_alert_seq is None:
        # Partial credit when cause signals exist but no formal alert followed
        second_signals = [
            e
            for e in facts.events
            if any(
                e.event_type == item.event_type
                and (item.asset_id is None or e.asset_id == item.asset_id)
                for item in expected
            )
            and e.sequence > first_signal_seq
        ]
        if second_signals:
            delay = second_signals[0].sequence - first_signal_seq
            raw = 0.55 if delay <= 40 else 0.35 if delay <= 80 else 0.2
            reason = (
                f"No formal alert; detection inferred from subsequent true-cause signal "
                f"with sequence delay {delay}."
            )
            event_ids = [first_signal_event or "", second_signals[0].event_id]
            seq = second_signals[0].sequence
        else:
            raw = 0.15
            reason = "True-cause signal observed but no credible detection followed."
            event_ids = [first_signal_event] if first_signal_event else []
            seq = first_signal_seq
    else:
        delay = first_alert_seq - first_signal_seq
        if delay <= 20:
            raw = 1.0
        elif delay <= 40:
            raw = 0.85
        elif delay <= 80:
            raw = 0.65
        elif delay <= 120:
            raw = 0.4
        else:
            raw = 0.2
        reason = (
            f"Detection delay from first true-cause signal to first alert was {delay} sequences."
        )
        event_ids = [x for x in [first_signal_event, first_alert_id] if x]
        seq = first_alert_seq

    return _component(
        "criterion-detection-speed",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [_explanation(rule_id, reason, event_ids=event_ids, sequence=seq)],
    )


def score_evidence_coverage(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> tuple[ScoreComponentV1, list[dict[str, object]]]:
    rule_id = "rule-evidence-coverage-fraction"
    expected = _true_cause_expected(facts)
    missed: list[dict[str, object]] = []
    if not expected:
        component = _component(
            "criterion-evidence-coverage",
            label,
            weight,
            0.0,
            max_score,
            [rule_id],
            [_explanation(rule_id, "No expected evidence defined for the true cause.")],
        )
        return component, missed

    discovered_count = 0
    cited_events: list[str] = []
    cited_evidence: list[str] = []
    for item in expected:
        discovered, event_ids, evidence_ids, bookmark = _evidence_discovered(facts, item)
        if discovered:
            discovered_count += 1
            cited_events.extend(event_ids)
            cited_evidence.extend(evidence_ids)
        missed.append(
            {
                "expectedEvidenceKey": item.key,
                "eventType": item.event_type,
                "assetId": item.asset_id,
                "description": item.description,
                "discovered": discovered,
                "relatedEventIds": event_ids,
                "relatedEvidenceIds": evidence_ids,
                "bookmarkSequence": bookmark,
            }
        )

    raw = discovered_count / len(expected)
    reason = f"Discovered {discovered_count} of {len(expected)} expected true-cause evidence items."
    component = _component(
        "criterion-evidence-coverage",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [
            _explanation(
                rule_id,
                reason,
                event_ids=cited_events[:8],
                evidence_ids=cited_evidence[:8],
            )
        ],
    )
    return component, missed


def score_hypothesis_quality(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-hypothesis-true-cause"
    if not facts.true_cause_id:
        return _component(
            "criterion-hypothesis-quality",
            label,
            weight,
            0.0,
            max_score,
            [rule_id],
            [_explanation(rule_id, "True cause unknown; hypothesis quality cannot be graded.")],
        )

    cause_tokens = {
        facts.true_cause_id.lower(),
        facts.true_cause_id.replace("hidden-cause-", "").replace("-", " ").lower(),
    }
    if facts.true_cause_label:
        cause_tokens.add(facts.true_cause_label.lower())

    best_raw = 0.0
    best_hyp = None
    distractor_penalty = 0.0
    for hyp in facts.hypotheses:
        statement = (hyp.statement or "").lower()
        matched = any(token and token in statement for token in cause_tokens)
        if matched:
            conf = hyp.confidence if hyp.confidence is not None else 0.7
            candidate = 0.7 + 0.3 * conf
            if candidate > best_raw:
                best_raw = candidate
                best_hyp = hyp
        else:
            # Distractor-only hypothesis with high confidence is penalized later via average
            if (hyp.confidence or 0) >= 0.7:
                distractor_penalty = max(distractor_penalty, 0.25)

    if best_hyp is None and facts.hypotheses:
        raw = max(0.0, 0.25 - distractor_penalty)
        reason = "Hypotheses present but none identified the true root cause."
        hyp_ids = [h.hypothesis_id for h in facts.hypotheses[:3]]
    elif best_hyp is None:
        raw = 0.1
        reason = "No hypotheses were recorded for the run."
        hyp_ids = []
    else:
        raw = max(0.0, best_raw - distractor_penalty * 0.5)
        reason = (
            f"Best hypothesis matched the true cause "
            f"({facts.true_cause_label or facts.true_cause_id}) with confidence "
            f"{best_hyp.confidence}."
        )
        hyp_ids = [best_hyp.hypothesis_id]

    return _component(
        "criterion-hypothesis-quality",
        label,
        weight,
        raw,
        max_score,
        [rule_id, "rule-hypothesis-distractor-penalty"],
        [_explanation(rule_id, reason, hypothesis_ids=hyp_ids)],
    )


def score_false_positive_cost(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-false-positive-containment-penalty"
    expected_assets = {e.asset_id for e in _true_cause_expected(facts) if e.asset_id}
    penalty = 0.0
    cited_proposals: list[str] = []
    for action in facts.executed_actions:
        targets = set(action.target_asset_ids)
        if not targets:
            continue
        # Containment on assets unrelated to true-cause evidence chain
        if expected_assets and targets.isdisjoint(expected_assets):
            if "contain" in action.outcome.lower() or action.impact_score >= 0.5:
                penalty += 0.35
                cited_proposals.append(action.proposal_id)
        elif not expected_assets and action.impact_score >= 0.8:
            penalty += 0.2
            cited_proposals.append(action.proposal_id)

    raw = max(0.0, 1.0 - min(1.0, penalty))
    reason = (
        "No distractor-driven containment detected."
        if penalty == 0
        else f"Applied false-positive containment penalty of {min(1.0, penalty):.2f}."
    )
    return _component(
        "criterion-false-positive-cost",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [_explanation(rule_id, reason, proposal_ids=cited_proposals[:5])],
    )


def score_response_proportionality(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-response-branch-alignment"
    branch = facts.selected_response_branch
    if not branch:
        # Infer from executed actions / proposals
        summaries = " ".join(p.summary.lower() for p in facts.proposals)
        if "remediat" in summaries:
            branch = "branch-response-remediate"
        elif "investigat" in summaries:
            branch = "branch-response-investigate"
        elif "contain" in summaries:
            branch = "branch-response-contain"

    # Cause-aware preferred branches (evidence-grounded; multiple can score well)
    preferred: dict[str, tuple[str, ...]] = {
        "hidden-cause-compromised-credentials": (
            "branch-response-contain",
            "branch-response-remediate",
        ),
        "hidden-cause-undocumented-maintenance": (
            "branch-response-investigate",
            "branch-response-remediate",
        ),
        "hidden-cause-defective-deployment": (
            "branch-response-remediate",
            "branch-response-investigate",
        ),
        "hidden-cause-internal-misuse": (
            "branch-response-contain",
            "branch-response-investigate",
        ),
    }
    cause = facts.true_cause_id or ""
    good = preferred.get(cause, tuple(b.branch_id for b in facts.response_branches))

    if branch and branch in good:
        raw = 1.0 if branch == (good[0] if good else branch) else 0.85
        reason = f"Selected response branch {branch} is evidence-grounded for the true cause."
    elif branch:
        raw = 0.45
        reason = f"Selected response branch {branch} is suboptimal but recorded."
    else:
        raw = 0.2
        reason = "No response branch selection or response proposals were recorded."

    return _component(
        "criterion-response-proportionality",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [_explanation(rule_id, reason)],
    )


def score_service_impact(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-service-impact-from-actions"
    if not facts.executed_actions:
        return _component(
            "criterion-service-impact",
            label,
            weight,
            0.7,
            max_score,
            [rule_id],
            [
                _explanation(
                    rule_id,
                    "No executed actions; moderate credit for avoiding unnecessary disruption.",
                )
            ],
        )

    avg_impact = sum(a.impact_score for a in facts.executed_actions) / len(facts.executed_actions)
    # Lower impact is better when response still happened
    raw = max(0.0, 1.0 - avg_impact)
    # Contain branch naturally higher impact — slight floor if proportionate
    if facts.selected_response_branch == "branch-response-contain":
        raw = max(raw, 0.35)
    # "Estimated", not "measured": nothing instruments the real service impact of an
    # action. The assembler infers this figure from each action's result summary (see
    # `_estimate_action_impact`), so the explanation must not tell the operator their
    # grade rests on a measurement the platform never took.
    reason = f"Average estimated action impact score was {avg_impact:.2f} (lower is better)."
    return _component(
        "criterion-service-impact",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [
            _explanation(
                rule_id,
                reason,
                proposal_ids=[a.proposal_id for a in facts.executed_actions[:5]],
            )
        ],
    )


def score_recurrence(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-recurrence-handling"
    expected = _true_cause_expected(facts)
    if not expected:
        return _component(
            "criterion-recurrence",
            label,
            weight,
            0.5,
            max_score,
            [rule_id],
            [_explanation(rule_id, "Insufficient cause evidence to evaluate recurrence.")],
        )

    # Count repeated true-cause signal types after first occurrence
    seen: dict[str, int] = {}
    for event in facts.events:
        for item in expected:
            if event.event_type == item.event_type and (
                item.asset_id is None or event.asset_id == item.asset_id
            ):
                key = f"{item.event_type}:{item.asset_id}"
                seen[key] = seen.get(key, 0) + 1

    repeated = {k: v for k, v in seen.items() if v > 1}
    if not repeated:
        raw = 0.8
        reason = "No repeated true-cause signals after initial detection."
    elif facts.executed_actions or any(
        p.status in {"approved", "executed"} for p in facts.proposals
    ):
        raw = 0.9
        reason = "Repeated true-cause signals were addressed by response actions."
    else:
        raw = 0.3
        reason = "Repeated true-cause signals occurred without recorded response."

    return _component(
        "criterion-recurrence",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [_explanation(rule_id, reason)],
    )


def score_objectives(
    facts: ScoringFacts, weight: float, label: str, max_score: float
) -> ScoreComponentV1:
    rule_id = "rule-objectives-completion"
    if not facts.objectives:
        return _component(
            "criterion-objectives",
            label,
            weight,
            0.0,
            max_score,
            [rule_id],
            [_explanation(rule_id, "No scenario objectives declared.")],
        )

    met = 0
    notes: list[str] = []
    # objective-detect-cause
    for obj in facts.objectives:
        oid = obj.objective_id
        if "detect" in oid or "cause" in oid:
            ok = any(
                facts.true_cause_id
                and facts.true_cause_id.replace("hidden-cause-", "").replace("-", " ")
                in (h.statement or "").lower()
                for h in facts.hypotheses
            ) or any(
                facts.true_cause_label
                and facts.true_cause_label.lower() in (h.statement or "").lower()
                for h in facts.hypotheses
            )
            # Also pass if evidence coverage was complete
            expected = _true_cause_expected(facts)
            if expected:
                discovered = sum(1 for e in expected if _evidence_discovered(facts, e)[0])
                ok = ok or discovered == len(expected)
            if ok:
                met += 1
                notes.append(f"{oid}: met")
            else:
                notes.append(f"{oid}: missed")
        elif "proportion" in oid or "response" in oid:
            ok = bool(facts.executed_actions or facts.approvals or facts.selected_response_branch)
            if ok:
                met += 1
                notes.append(f"{oid}: met")
            else:
                notes.append(f"{oid}: missed")
        elif "evidence" in oid or "preserve" in oid:
            ok = len(facts.evidence) > 0
            if ok:
                met += 1
                notes.append(f"{oid}: met")
            else:
                notes.append(f"{oid}: missed")
        else:
            # Generic: credit if any evidence and any decision
            ok = bool(facts.evidence) and bool(facts.approvals or facts.proposals)
            if ok:
                met += 1
                notes.append(f"{oid}: met")
            else:
                notes.append(f"{oid}: missed")

    raw = met / len(facts.objectives)
    reason = f"Objectives met {met}/{len(facts.objectives)}. " + "; ".join(notes)
    return _component(
        "criterion-objectives",
        label,
        weight,
        raw,
        max_score,
        [rule_id],
        [_explanation(rule_id, reason)],
    )


CRITERION_HANDLERS = {
    "criterion-detection-speed": score_detection_speed,
    "criterion-hypothesis-quality": score_hypothesis_quality,
    "criterion-false-positive-cost": score_false_positive_cost,
    "criterion-response-proportionality": score_response_proportionality,
    "criterion-service-impact": score_service_impact,
    "criterion-recurrence": score_recurrence,
    "criterion-objectives": score_objectives,
}
