"""Deterministic alert correlation for WATCHTOWER triage."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from aegis_contracts.entities import AlertV1
from aegis_contracts.investigation import AlertCorrelationDecisionV1

TEMPORAL_PROXIMITY_WINDOW = timedelta(minutes=15)
SHARED_ASSET_DECISION = "group_shared_asset"
TEMPORAL_PROXIMITY_DECISION = "group_temporal_proximity"
SEPARATED_DECISION = "separate"


def correlate_alerts(alerts: list[AlertV1]) -> list[AlertCorrelationDecisionV1]:
    """Return deterministic correlation decisions for the supplied alerts."""
    if not alerts:
        return []

    sorted_alerts = sorted(alerts, key=lambda item: (item.created_at, item.id))
    decisions: list[AlertCorrelationDecisionV1] = []
    seen_pairs: set[tuple[str, str]] = set()

    by_asset: dict[str, list[AlertV1]] = defaultdict(list)
    for alert in sorted_alerts:
        by_asset[alert.asset_id].append(alert)

    for asset_id, asset_alerts in sorted(by_asset.items()):
        if len(asset_alerts) < 2:
            continue
        alert_ids = [alert.id for alert in asset_alerts]
        decisions.append(
            AlertCorrelationDecisionV1(
                alert_ids=alert_ids,
                decision=SHARED_ASSET_DECISION,
                rationale=(
                    f"Alerts reference the same asset ({asset_id}) "
                    "and are treated as one incident thread."
                ),
                factors=["shared_asset", asset_id],
            )
        )
        for left in alert_ids:
            for right in alert_ids:
                if left < right:
                    seen_pairs.add((left, right))

    for index, left in enumerate(sorted_alerts):
        for right in sorted_alerts[index + 1 :]:
            pair_key = tuple(sorted((left.id, right.id)))
            if pair_key in seen_pairs:
                continue
            delta = abs(right.created_at - left.created_at)
            if delta <= TEMPORAL_PROXIMITY_WINDOW:
                decisions.append(
                    AlertCorrelationDecisionV1(
                        alert_ids=[left.id, right.id],
                        decision=TEMPORAL_PROXIMITY_DECISION,
                        rationale=(
                            "Alerts occurred within the temporal proximity window "
                            f"({int(TEMPORAL_PROXIMITY_WINDOW.total_seconds())} seconds)."
                        ),
                        factors=[
                            "temporal_proximity",
                            left.asset_id,
                            right.asset_id,
                        ],
                    )
                )
                seen_pairs.add(pair_key)

    grouped_ids = {alert_id for decision in decisions for alert_id in decision.alert_ids}
    for alert in sorted_alerts:
        if alert.id in grouped_ids:
            continue
        decisions.append(
            AlertCorrelationDecisionV1(
                alert_ids=[alert.id],
                decision=SEPARATED_DECISION,
                rationale=(
                    "Alert has no shared-asset or temporal-proximity "
                    "correlation with other alerts."
                ),
                factors=["isolated_alert"],
            )
        )

    return sorted(
        decisions,
        key=lambda item: (item.decision, item.alert_ids[0] if item.alert_ids else ""),
    )


def derive_grouped_and_separated_alert_ids(
    alerts: list[AlertV1],
    decisions: list[AlertCorrelationDecisionV1],
) -> tuple[list[str], list[str]]:
    """Partition alert IDs into grouped and separated sets from correlation decisions."""
    grouped: set[str] = set()
    separated: set[str] = set()
    for decision in decisions:
        if decision.decision == SEPARATED_DECISION:
            separated.update(decision.alert_ids)
        else:
            grouped.update(decision.alert_ids)

    all_alert_ids = {alert.id for alert in alerts}
    for alert_id in all_alert_ids:
        if alert_id not in grouped and alert_id not in separated:
            separated.add(alert_id)

    return sorted(grouped), sorted(separated)
