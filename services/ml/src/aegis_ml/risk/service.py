"""ML service orchestration for graph risk propagation."""

from __future__ import annotations

from datetime import datetime

from aegis_contracts.graph import GraphSnapshotV1
from aegis_contracts.risk import RiskEngineConfigV1, RiskInputV1
from aegis_graph_risk import RiskPropagationResult, compute_risk_scores


def compute_graph_risk(
    snapshot: GraphSnapshotV1,
    signals: list[RiskInputV1],
    config: RiskEngineConfigV1,
    *,
    current_sim_time: datetime,
    computed_at_sequence: int,
    incident_seed_asset_ids: list[str] | None = None,
) -> RiskPropagationResult:
    return compute_risk_scores(
        snapshot,
        signals,
        config,
        current_sim_time=current_sim_time,
        computed_at_sequence=computed_at_sequence,
        incident_seed_asset_ids=incident_seed_asset_ids,
    )
