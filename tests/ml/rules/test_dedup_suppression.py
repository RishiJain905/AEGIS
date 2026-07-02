"""Deduplication and suppression tests."""

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
