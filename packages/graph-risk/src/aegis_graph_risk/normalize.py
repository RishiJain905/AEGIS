"""Normalize Phase 15/16 detection outputs into risk inputs."""

from __future__ import annotations

from datetime import datetime

from aegis_contracts.entities import AlertV1, ModelScoreV1
from aegis_contracts.risk import RiskInputV1, RiskSignalSourceType, RiskSignalStatus
from aegis_contracts.versioning import RISK_INPUT_SCHEMA_VERSION

#: How much risk an alert asserts, by severity. ``RiskInputV1`` carries *strength* (how bad
#: the thing being claimed is) and *confidence* (how sure the detector is) as two separate
#: fields, and the engine multiplies them. The normalizer used to put ``alert.confidence``
#: in both, which squared the confidence and threw severity away entirely — every alert in
#: a run contributed the same amount no matter what it was reporting.
#:
#: ``AlertV1.severity`` is a free-form string across the detection contracts, so the ladder
#: is matched case-insensitively with a mid-scale fallback for anything unrecognized: an
#: alert nobody taught us to read is still an alert, and dropping it to zero would silently
#: delete a detection from the risk picture.
ALERT_SEVERITY_STRENGTH: dict[str, float] = {
    "informational": 0.15,
    "info": 0.15,
    "low": 0.30,
    "medium": 0.55,
    "high": 0.80,
    "critical": 1.00,
}

#: Strength for a severity outside :data:`ALERT_SEVERITY_STRENGTH`, and confidence for an
#: alert whose detector did not report one.
UNKNOWN_SEVERITY_STRENGTH = 0.5
DEFAULT_ALERT_CONFIDENCE = 0.5


def alert_severity_strength(severity: str) -> float:
    """Risk strength asserted by an alert of this severity."""
    return ALERT_SEVERITY_STRENGTH.get(severity.strip().lower(), UNKNOWN_SEVERITY_STRENGTH)


def normalize_alert_to_risk_input(alert: AlertV1, *, sim_time: datetime) -> RiskInputV1:
    strength = alert_severity_strength(alert.severity)
    confidence = alert.confidence if alert.confidence is not None else DEFAULT_ALERT_CONFIDENCE
    dedup = alert.deduplication_key or f"{alert.run_id}:{alert.id}"
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id=f"risk-sig-alert-{alert.id}",
        run_id=alert.run_id,
        source_type=RiskSignalSourceType.RULE,
        asset_id=alert.asset_id,
        strength=min(1.0, max(0.0, strength)),
        confidence=min(1.0, max(0.0, confidence)),
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
