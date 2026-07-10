"""Acceptance criteria mapping for Phase 29 scoring."""

from __future__ import annotations

from pathlib import Path

from aegis_contracts.scoring import ScoreExportFormatV1
from aegis_scoring.engine import compute_run_score
from aegis_scoring.export import render_score_export
from aegis_scoring.facts import (
    EventFact,
    EvidenceFact,
    HypothesisFact,
    ScoringFacts,
)
from aegis_scoring.rubric_loader import (
    build_rubric_from_manifest,
    load_expected_evidence,
    load_objectives,
    load_response_branches,
    load_yaml,
)
from aegis_scoring.view_model import build_after_action_view_model

SCENARIO = Path("scenarios/operation-silent-relay")


def _facts() -> ScoringFacts:
    manifest = load_yaml(SCENARIO / "manifest.yaml")
    return ScoringFacts(
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
                25,
                "telemetry.authentication.succeeded",
                "asset:svc-logistics-api",
                None,
            ),
            EventFact(
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA3",
                40,
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
                "auth",
            ),
            EvidenceFact(
                "evidence:evd_002",
                "evt_01ARZ3NDEKTSV4RRFFQ69G5FA2",
                "asset:svc-logistics-api",
                "lateral",
            ),
        ],
        hypotheses=[
            HypothesisFact(
                "hyp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "Compromised service account credentials",
                0.85,
                "active",
                1,
            )
        ],
        expected_evidence=load_expected_evidence(SCENARIO / "expected-evidence.yaml"),
        objectives=load_objectives(manifest),
        response_branches=load_response_branches(manifest),
        true_cause_id="hidden-cause-compromised-credentials",
        true_cause_label="Compromised service account credentials",
        selected_response_branch="branch-response-contain",
        calculated_at="2026-07-10T18:00:00.000Z",
        lessons=["Preserve contradictory hypotheses during after-action review."],
        scribe_report_id="aar_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        scribe_version_number=1,
    )


def test_ac1_golden_branches_produce_reproducible_attributed_scores() -> None:
    facts = _facts()
    a = compute_run_score(
        facts, score_id="scr_01ARZ3NDEKTSV4RRFFQ69G5FAV", calculated_at=facts.calculated_at
    )
    b = compute_run_score(
        facts, score_id="scr_01ARZ3NDEKTSV4RRFFQ69G5FAV", calculated_at=facts.calculated_at
    )
    assert a.overall_score == b.overall_score
    assert a.provenance.fingerprint == b.provenance.fingerprint
    assert a.components


def test_ac2_alternative_valid_evidence_grounded_responses_can_score_well() -> None:
    contain = compute_run_score(_facts())
    investigate_facts = _facts()
    investigate_facts.selected_response_branch = "branch-response-investigate"
    investigate = compute_run_score(investigate_facts)
    assert contain.passed and investigate.passed
    assert contain.valid_alternatives


def test_ac3_every_component_explainable_from_source_records() -> None:
    score = compute_run_score(_facts())
    for component in score.components:
        assert component.explanations
        assert component.rule_ids


def test_ac4_after_action_review_teaches_what_happened() -> None:
    facts = _facts()
    score = compute_run_score(facts, calculated_at=facts.calculated_at)
    view = build_after_action_view_model(facts, score)
    assert view.score.hidden_cause_revealed
    assert view.lessons
    assert view.bookmarks
    content, artifact = render_score_export(score, ScoreExportFormatV1.MARKDOWN)
    assert b"Grading engine" in content or b"grading" in content.lower()
    assert artifact.integrity_checksum
    assert artifact.grading_engine_version
