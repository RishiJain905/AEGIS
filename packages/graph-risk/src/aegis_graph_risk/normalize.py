"""Normalize Phase 15/16 detection outputs into risk inputs."""

from __future__ import annotations

from datetime import datetime

from aegis_contracts.entities import AlertV1, ModelScoreV1
from aegis_contracts.risk import RiskInputV1, RiskSignalSourceType, RiskSignalStatus
from aegis_contracts.versioning import RISK_INPUT_SCHEMA_VERSION


def normalize_alert_to_risk_input(alert: AlertV1, *, sim_time: datetime) -> RiskInputV1:
    strength = alert.confidence if alert.confidence is not None else 0.5
    dedup = alert.deduplication_key or f"{alert.run_id}:{alert.id}"
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id=f"risk-sig-alert-{alert.id}",
        run_id=alert.run_id,
        source_type=RiskSignalSourceType.RULE,
        asset_id=alert.asset_id,
        strength=min(1.0, max(0.0, strength)),
        confidence=min(1.0, max(0.0, strength)),
        sim_time=sim_time,
        deduplication_key=dedup,
        status=RiskSignalStatus.ACTIVE,
        provenance_ref=alert.id,
        detector_id=alert.detector_id,
        rule_id=alert.rule_id,
    )


def normalize_model_score_to_risk_input(
    score: ModelScoreV1,
    *,
    run_id: str,
    sim_time: datetime,
    is_anomaly: bool = True,
    deduplication_key: str | None = None,
) -> RiskInputV1 | None:
    if not is_anomaly:
        return None
    dedup = deduplication_key or (
        f"{run_id}:model:{score.entity_id}:{int(sim_time.timestamp())}"
    )
    signal_id = f"risk-sig-model-{score.model_version_id}-{score.entity_id}"
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id=signal_id,
        run_id=run_id,
        source_type=RiskSignalSourceType.MODEL,
        asset_id=score.entity_id,
        strength=min(1.0, max(0.0, score.score)),
        confidence=min(1.0, max(0.0, score.score)),
        sim_time=sim_time,
        deduplication_key=dedup,
        status=RiskSignalStatus.ACTIVE,
        provenance_ref=score.source_event_id or signal_id,
        detector_id="isolation-forest",
        rule_id=None,
    )


def deduplicate_risk_inputs(inputs: list[RiskInputV1]) -> list[RiskInputV1]:
    """Keep the latest signal per deduplication key (lexicographic signal_id tie-break)."""
    by_key: dict[str, RiskInputV1] = {}
    for item in sorted(inputs, key=lambda value: (value.deduplication_key, value.signal_id)):
        by_key[item.deduplication_key] = item
    return sorted(by_key.values(), key=lambda value: value.signal_id)
