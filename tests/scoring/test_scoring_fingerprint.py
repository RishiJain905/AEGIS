"""Regression tests for AEGIS-BUG-004: lossy scoring fingerprint collision.

Two authoritative fact sets that produce different scores must never share a
fingerprint, otherwise ``ScoringService`` returns a stale score for changed
facts. The offending field here is ``executed_actions[].target_asset_ids`` —
score-affecting (it drives false-positive-cost) yet absent from the previous
input checksum, so both fact sets collided on one fingerprint.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from aegis_scoring.engine import compute_run_score
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
from aegis_scoring.service import ScoringService

SCENARIO = Path("scenarios/operation-silent-relay")


def _facts(*, target_asset_ids: tuple[str, ...]) -> ScoringFacts:
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
                target_asset_ids,
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
                target_asset_ids,
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


# Containment on a true-cause asset (no false-positive penalty).
_ON_TRUE_CAUSE = ("asset:svc-logistics-api",)
# Containment on an unrelated asset (false-positive penalty applies).
_OFF_TRUE_CAUSE = ("asset:printer-lobby-01",)


class _FakeRunScores:
    def __init__(self) -> None:
        self._by_fingerprint: dict[str, object] = {}
        self._by_run: dict[str, object] = {}

    async def get_by_fingerprint(self, fingerprint: str) -> object | None:
        return self._by_fingerprint.get(fingerprint)

    async def get_latest_for_run(self, run_id: str) -> object | None:
        return self._by_run.get(run_id)

    async def add(self, score: object) -> None:
        fingerprint = score.provenance.fingerprint  # type: ignore[attr-defined]
        self._by_fingerprint[fingerprint] = score
        self._by_run[score.run_id] = score  # type: ignore[attr-defined]


class _FakeUow:
    def __init__(self) -> None:
        self.run_scores = _FakeRunScores()


def test_target_asset_ids_change_shifts_score_and_fingerprint() -> None:
    on_chain = compute_run_score(_facts(target_asset_ids=_ON_TRUE_CAUSE))
    off_chain = compute_run_score(_facts(target_asset_ids=_OFF_TRUE_CAUSE))

    # The mutated field genuinely changes the authoritative score...
    assert on_chain.overall_score != off_chain.overall_score
    # ...so the two scorings must never collide on one fingerprint.
    assert on_chain.provenance.fingerprint != off_chain.provenance.fingerprint
    assert on_chain.provenance.input_checksum != off_chain.provenance.input_checksum


def test_fingerprint_is_deterministic_for_identical_facts() -> None:
    first = compute_run_score(_facts(target_asset_ids=_ON_TRUE_CAUSE))
    second = compute_run_score(_facts(target_asset_ids=_ON_TRUE_CAUSE))
    assert first.provenance.fingerprint == second.provenance.fingerprint
    assert first.provenance.input_checksum == second.provenance.input_checksum


def test_evidence_summary_change_changes_fingerprint() -> None:
    base = _facts(target_asset_ids=_ON_TRUE_CAUSE)
    mutated = _facts(target_asset_ids=_ON_TRUE_CAUSE)
    mutated.evidence[1] = dataclasses.replace(
        mutated.evidence[1], summary="telemetry.authentication.succeeded lateral movement"
    )
    base_score = compute_run_score(base)
    mutated_score = compute_run_score(mutated)
    # evidence.summary feeds coverage matching yet was omitted from the old checksum.
    assert base_score.provenance.input_checksum != mutated_score.provenance.input_checksum


@pytest.mark.asyncio
async def test_service_does_not_return_stale_score_for_changed_facts(monkeypatch) -> None:
    service = ScoringService()
    uow = _FakeUow()

    facts_holder = {"facts": _facts(target_asset_ids=_ON_TRUE_CAUSE)}

    async def _fake_assemble(*_args: object, **_kwargs: object) -> ScoringFacts:
        return facts_holder["facts"]

    monkeypatch.setattr("aegis_scoring.service.assemble_scoring_facts", _fake_assemble)

    first = await service.score_run(uow, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV")

    # Change only the previously-uncovered field; the score changes.
    facts_holder["facts"] = _facts(target_asset_ids=_OFF_TRUE_CAUSE)
    second = await service.score_run(uow, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV")

    assert first.provenance.fingerprint != second.provenance.fingerprint
    assert second.overall_score != first.overall_score
    # The fresh (non-stale) score is returned, not the previously stored one.
    expected = compute_run_score(_facts(target_asset_ids=_OFF_TRUE_CAUSE))
    assert second.overall_score == expected.overall_score
