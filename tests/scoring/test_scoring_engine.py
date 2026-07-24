"""Unit tests for deterministic scoring engine."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts.scoring import ScoreErrorCode
from aegis_scoring.engine import compute_run_score
from aegis_scoring.errors import ScoringError
from aegis_scoring.facts import (
    ApprovalFact,
    EventFact,
    EvidenceFact,
    ExecutedActionFact,
    HypothesisFact,
    ProposalFact,
    ScoringFacts,
)
from aegis_scoring.rubric_loader import (
    build_rubric_from_manifest,
    load_expected_evidence,
    load_objectives,
    load_response_branches,
    load_yaml,
)

SCENARIO = Path("scenarios/operation-silent-relay")


def _base_facts(**overrides: object) -> ScoringFacts:
    manifest = load_yaml(SCENARIO / "manifest.yaml")
    facts = ScoringFacts(
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        run_status="completed",
        scenario_id="scenario:operation-silent-relay",
        scenario_version="1.0.0",
        rubric=build_rubric_from_manifest(manifest),
        events=[
            EventFact(
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA1",
                10,
                "telemetry.authentication.failed",
                "asset:svc-identity-broker",
                None,
            ),
            EventFact(
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA2",
                20,
                "telemetry.authentication.succeeded",
                "asset:svc-logistics-api",
                None,
            ),
            EventFact(
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA3",
                35,
                "alert.created",
                "asset:svc-identity-broker",
                None,
            ),
        ],
        evidence=[
            EvidenceFact(
                "evidence:evd_001",
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA1",
                "asset:svc-identity-broker",
                "auth failures",
            ),
            EvidenceFact(
                "evidence:evd_002",
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA2",
                "asset:svc-logistics-api",
                "lateral auth",
            ),
        ],
        hypotheses=[
            HypothesisFact(
                "hyp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "Compromised service account credentials caused lateral movement",
                0.9,
                "active",
                1,
            )
        ],
        proposals=[
            ProposalFact(
                "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "contain",
                "approved",
                "contain logistics API",
                ("asset:svc-logistics-api",),
                None,
                "require_approval",
            )
        ],
        approvals=[
            ApprovalFact(
                "apr_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "approved",
                50,
            )
        ],
        executed_actions=[
            ExecutedActionFact(
                "act_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                55,
                "contained with moderate impact",
                0.4,
                ("asset:svc-logistics-api",),
            )
        ],
        expected_evidence=load_expected_evidence(SCENARIO / "expected-evidence.yaml"),
        objectives=load_objectives(manifest),
        response_branches=load_response_branches(manifest),
        true_cause_id="hidden-cause-compromised-credentials",
        true_cause_label="Compromised service account credentials",
        selected_response_branch="branch-response-contain",
        incident_id="incident:silent-relay-001",
        calculated_at="2026-07-10T18:00:00.000Z",
    )
    for key, value in overrides.items():
        setattr(facts, key, value)
    return facts


def test_golden_branch_reproducible_attributed_scores() -> None:
    facts = _base_facts()
    first = compute_run_score(
        facts,
        score_id="scr_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        calculated_at="2026-07-10T18:00:00.000Z",
    )
    second = compute_run_score(
        facts,
        score_id="scr_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        calculated_at="2026-07-10T18:00:00.000Z",
    )
    assert first.overall_score == second.overall_score
    assert first.provenance.fingerprint == second.provenance.fingerprint
    assert first.provenance.integrity_checksum == second.provenance.integrity_checksum
    assert all(component.explanations for component in first.components)
    assert first.provenance.grading_engine_version
    assert first.provenance.rubric_version
    assert first.provenance.scenario_version


def test_alternative_valid_response_can_score_well() -> None:
    contain = compute_run_score(_base_facts(selected_response_branch="branch-response-contain"))
    remediate = compute_run_score(_base_facts(selected_response_branch="branch-response-remediate"))
    assert contain.passed
    assert remediate.passed
    assert any(not alt.authoritative for alt in contain.valid_alternatives)
    assert all(
        "Counterfactual" in alt.description or "not a fact" in alt.description
        for alt in contain.valid_alternatives
    )


def test_every_component_explainable_from_source_records() -> None:
    score = compute_run_score(_base_facts())
    for component in score.components:
        assert component.rule_ids
        assert component.explanations
        for explanation in component.explanations:
            assert explanation.rule_id
            assert explanation.reason


def test_incomplete_run_fails_closed() -> None:
    with pytest.raises(ScoringError) as exc:
        compute_run_score(_base_facts(run_status="running"))
    assert exc.value.code == ScoreErrorCode.SCORE_INCOMPLETE_RUN


def test_stopped_run_is_scoreable() -> None:
    # An operator-stopped run is terminal and must still produce a score/debrief,
    # matching lifecycle.finalize_stopped_run and the operator-profile assembler.
    score = compute_run_score(_base_facts(run_status="stopped"))
    assert score.overall_score >= 0


def test_correct_rejection_earns_restraint_credit() -> None:
    facts = _base_facts(
        approvals=[
            ApprovalFact(
                "apr_01ARZ3NDEKTSV4RRFFQ69G5FB1",
                "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "rejected",
                50,
            )
        ],
        proposals=[
            ProposalFact(
                "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "contain",
                "rejected",
                "unsafe contain",
                ("asset:svc-logistics-api",),
                None,
                "deny",
            )
        ],
        executed_actions=[],
    )
    score = compute_run_score(facts)
    assert any(r.outcome.value == "restraint_credited" for r in score.decision_reviews)
    assert all(r.used_future_knowledge is False for r in score.decision_reviews)
