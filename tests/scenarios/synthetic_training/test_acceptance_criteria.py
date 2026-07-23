"""Tutorial acceptance criteria for the Synthetic Training Scenario package."""

from __future__ import annotations

import yaml

from .helpers import GOLDEN_SEEDS_PATH, SCENARIO, load_golden_seeds


def _manifest() -> dict:
    return yaml.safe_load((SCENARIO / "manifest.yaml").read_text(encoding="utf-8"))


def test_pinned_tutorial_seed_and_horizon() -> None:
    registry = load_golden_seeds()
    assert registry["simulationSteps"] == 120
    seeds = registry["seeds"]
    assert len(seeds) == 1
    assert seeds[0]["seed"] == 1000
    assert seeds[0]["attackBranch"] == "branch-attack-primary"


def test_single_attack_branch_no_rng() -> None:
    manifest = _manifest()
    branches = manifest["branches"]
    assert len(branches) == 1
    assert branches[0]["id"] == "branch-attack-primary"
    assert branches[0]["weight"] == 1.0


def test_compact_asset_set_across_a_few_zones() -> None:
    manifest = _manifest()
    assert 8 <= len(manifest["assets"]) <= 10
    assert 2 <= len(manifest["zones"]) <= 3


def test_hidden_conditions_use_fog_of_war_visibility() -> None:
    manifest = _manifest()
    conditions = manifest["hiddenConditions"]
    assert conditions
    for condition in conditions:
        assert condition["visibility"]["mode"] == "hidden_until_triggered"


def test_evidence_manifest_supports_and_contradicts() -> None:
    evidence = yaml.safe_load((SCENARIO / "expected-evidence.yaml").read_text(encoding="utf-8"))
    for cause_id, definition in evidence["causes"].items():
        assert definition["supportingEvidence"]
        assert definition["contradictsFalseHypotheses"]
        assert cause_id.startswith("hidden-cause-")


def test_scoring_rubric_authored() -> None:
    manifest = _manifest()
    scoring = manifest["scoring"]
    assert scoring["maxScore"] == 100
    assert scoring["rubric"]
    criteria = scoring["criteria"]
    assert all(0.0 <= c["weight"] <= 1.0 for c in criteria)
    assert abs(sum(c["weight"] for c in criteria) - 1.0) < 1e-9


def test_golden_seed_registry_file_exists() -> None:
    assert GOLDEN_SEEDS_PATH.exists()
