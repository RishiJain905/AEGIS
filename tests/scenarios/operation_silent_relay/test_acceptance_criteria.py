"""Phase 10 acceptance criteria tests."""

from __future__ import annotations

import yaml

from .helpers import (
    EVIDENCE_PATH,
    GOLDEN_SEEDS_PATH,
    SCENARIO,
    event_types_for_run,
    load_golden_seeds,
)


def test_golden_seeds_cover_each_cause_and_branch() -> None:
    registry = load_golden_seeds()
    causes = {entry["rootCauseBranch"] for entry in registry["seeds"]}
    responses = {entry["responseBranch"] for entry in registry["seeds"]}
    assert len(causes) == 4
    assert len(responses) == 3


def test_evidence_manifest_supports_and_contradicts() -> None:
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    for cause_id, definition in evidence["causes"].items():
        assert definition["supportingEvidence"]
        assert definition["contradictsFalseHypotheses"]
        assert cause_id.startswith("hidden-cause-")


def test_cause_signals_not_obvious_from_single_event() -> None:
    """Each cause requires multiple signal types before hidden condition triggers."""
    registry = load_golden_seeds()
    for entry in registry["seeds"]:
        if entry["seed"] < 1000:
            continue
        types = event_types_for_run(entry["seed"])
        assert "sim.branch.selected" in types
        assert len(types) > 5


def test_scoring_rubric_authored() -> None:
    manifest = yaml.safe_load((SCENARIO / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["scoring"]["maxScore"] == 100
    assert len(manifest["scoring"]["criteria"]) >= 7
    total_weight = sum(c["weight"] for c in manifest["scoring"]["criteria"])
    assert total_weight > 0


def test_golden_seed_registry_file_exists() -> None:
    assert GOLDEN_SEEDS_PATH.exists()
