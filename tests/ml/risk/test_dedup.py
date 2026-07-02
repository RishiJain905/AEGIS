"""Deduplication of risk inputs."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.risk import RiskInputV1, RiskSignalSourceType, RiskSignalStatus
from aegis_contracts.versioning import RISK_INPUT_SCHEMA_VERSION
from aegis_graph_risk import deduplicate_risk_inputs


def _input(signal_id: str, dedup_key: str, strength: float) -> RiskInputV1:
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id=signal_id,
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:a",
        strength=strength,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key=dedup_key,
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:test",
    )


def test_duplicate_dedup_keys_keep_latest_signal() -> None:
    first = _input("sig-a", "dup-key", 0.5)
    second = _input("sig-b", "dup-key", 0.9)
    result = deduplicate_risk_inputs([first, second])
    assert len(result) == 1
    assert result[0].signal_id == "sig-b"
    assert result[0].strength == 0.9


def test_distinct_dedup_keys_are_preserved() -> None:
    inputs = [_input("sig-a", "key-a", 0.5), _input("sig-b", "key-b", 0.7)]
    result = deduplicate_risk_inputs(inputs)
    assert len(result) == 2
