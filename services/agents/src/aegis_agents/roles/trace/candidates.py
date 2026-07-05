"""Affected-asset candidate ranking for TRACE."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.entities import AlertV1
from aegis_contracts.investigation import CandidateAffectedAssetV1
from aegis_contracts.risk import AssetRiskScoreV1
from aegis_contracts.versioning import CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION

from aegis_agents.runtime.ids import new_runtime_id

_SEVERITY_WEIGHTS = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.55,
    "low": 0.3,
    "info": 0.15,
}


def _severity_weight(severity: str) -> float:
    return _SEVERITY_WEIGHTS.get(severity.lower(), 0.4)


def _score_asset(
    *,
    asset_id: str,
    alerts: list[AlertV1],
    risk_by_asset: dict[str, AssetRiskScoreV1],
    evidence_ids: list[str],
    model_confidence: float | None,
) -> tuple[float, str]:
    asset_alerts = [alert for alert in alerts if alert.asset_id == asset_id]
    alert_score = max((_severity_weight(alert.severity) for alert in asset_alerts), default=0.0)
    risk_score = risk_by_asset.get(asset_id)
    risk_total = risk_score.total if risk_score is not None else 0.0
    confidence = (
        model_confidence
        if model_confidence is not None
        else min(1.0, 0.35 + alert_score + risk_total)
    )
    rationale_parts = []
    if asset_alerts:
        rationale_parts.append(f"{len(asset_alerts)} correlated alert(s)")
    if risk_score is not None:
        rationale_parts.append(f"risk total {risk_score.total:.2f}")
    if not rationale_parts:
        rationale_parts.append("selected during bounded TRACE expansion")
    return confidence, "; ".join(rationale_parts)


def rank_affected_assets(
    *,
    alerts: list[AlertV1],
    risk_scores: list[AssetRiskScoreV1],
    evidence_ids: list[str],
    candidates_from_model: list[dict[str, Any]],
    incident_id: str,
) -> list[CandidateAffectedAssetV1]:
    risk_by_asset = {score.asset_id: score for score in risk_scores}
    now = datetime.now(UTC)
    ranked: list[tuple[float, CandidateAffectedAssetV1]] = []

    model_asset_ids = {
        item["assetId"]: item for item in candidates_from_model if item.get("assetId")
    }
    candidate_asset_ids = list(model_asset_ids.keys())
    if not candidate_asset_ids:
        seen: set[str] = set()
        for alert in alerts:
            if alert.asset_id not in seen:
                seen.add(alert.asset_id)
                candidate_asset_ids.append(alert.asset_id)

    for asset_id in candidate_asset_ids:
        model_item = model_asset_ids.get(asset_id, {})
        confidence, rationale = _score_asset(
            asset_id=asset_id,
            alerts=alerts,
            risk_by_asset=risk_by_asset,
            evidence_ids=evidence_ids,
            model_confidence=model_item.get("confidence"),
        )
        if model_item.get("rationale"):
            rationale = str(model_item["rationale"])
        candidate_evidence_ids = list(model_item.get("evidenceIds", evidence_ids))
        ranked.append(
            (
                confidence,
                CandidateAffectedAssetV1(
                    schema_version=CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION,
                    id=new_runtime_id("cand"),
                    incident_id=incident_id,
                    asset_id=asset_id,
                    confidence=confidence,
                    evidence_ids=candidate_evidence_ids,
                    rationale=rationale,
                    created_at=now,
                ),
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in ranked]
