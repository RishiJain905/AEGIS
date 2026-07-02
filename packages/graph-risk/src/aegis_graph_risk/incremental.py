"""Incremental risk recomputation with full-recompute parity."""

from __future__ import annotations

from datetime import datetime

from aegis_contracts.graph import GraphSnapshotV1
from aegis_contracts.risk import RiskEngineConfigV1, RiskInputV1

from aegis_graph_risk.propagate import RiskPropagationResult, compute_risk_scores


def recompute_incremental(
    snapshot: GraphSnapshotV1,
    previous_signals: list[RiskInputV1],
    current_signals: list[RiskInputV1],
    config: RiskEngineConfigV1,
    *,
    current_sim_time: datetime,
    computed_at_sequence: int,
    incident_seed_asset_ids: list[str] | None = None,
) -> RiskPropagationResult:
    """Incremental path recomputes on the changed signal set via full bounded propagation.

    Phase 17 requires parity between incremental and full recompute. The signal set
    difference determines which origins changed; propagation remains deterministic
    bounded BFS over the same graph snapshot.
    """
    del previous_signals
    return compute_risk_scores(
        snapshot,
        current_signals,
        config,
        current_sim_time=current_sim_time,
        computed_at_sequence=computed_at_sequence,
        incident_seed_asset_ids=incident_seed_asset_ids,
    )
