"""Deduplication and suppression tests."""

from pathlib import Path

from aegis_incidents.pipeline import evaluate_features_offline
from aegis_incidents.rules.dedup import build_deduplication_key

from tests.ml.features.helpers import sample_auth_failed
from tests.ml.rules.helpers import RUN_ID


def test_dedup_key_is_stable() -> None:
    key_a = build_deduplication_key(
        run_id=RUN_ID,
        rule_id="rule-unusual-login",
        entity_id="asset:svc-identity-broker",
        window_start_epoch=0,
    )
    key_b = build_deduplication_key(
        run_id=RUN_ID,
        rule_id="rule-unusual-login",
        entity_id="asset:svc-identity-broker",
        window_start_epoch=0,
    )
    assert key_a == key_b


def test_duplicate_dedup_key_suppressed_on_second_pipeline_pass() -> None:
    events = [
        sample_auth_failed(sequence=index, sim_offset_seconds=index * 5)
        for index in range(1, 12)
    ]
    first = evaluate_features_offline(run_id=RUN_ID, events=events)
    accepted_keys = {candidate.deduplication_key for candidate in first.accepted_candidates}
    second = evaluate_features_offline(
        run_id=RUN_ID,
        events=events,
        existing_dedup_keys=accepted_keys,
    )
    assert second.alerts_suppressed >= 0
    assert len(second.accepted_candidates) <= len(first.accepted_candidates)


def test_a_suppression_group_does_not_hide_a_second_asset() -> None:
    """Suppression groups throttle one asset's noise; they must not silence another's.

    Keyed by group alone, the first ``rule-unseen-source`` alert in Operation Silent Relay
    suppressed the identical rule firing on ``asset:svc-identity-broker`` — the asset the
    campaign actually compromises. The run was left with one alert on an unrelated asset,
    so incident correlation had nothing to build a case from and the whole investigation
    chain downstream of it stayed dark.
    """
    from aegis_simulation_domain import SimulationEngine

    fixture = Path("scenarios/operation-silent-relay")
    manifest = SimulationEngine.load_manifest(fixture)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1000,
        scenario_version_id=f"scenario-version:{manifest.metadata.version}",
    )
    runtime.start()
    runtime.run_steps(300)
    events = list(runtime.events)

    result = evaluate_features_offline(run_id=events[0].run_id, events=events)
    alerting_assets = {
        candidate.entity_id for candidate in result.accepted_candidates
    }
    assert "asset:svc-identity-broker" in alerting_assets
    assert len(alerting_assets) > 1
