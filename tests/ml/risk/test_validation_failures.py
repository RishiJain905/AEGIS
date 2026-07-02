"""Validation failure paths."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts.errors import ContractValidationError
from aegis_contracts.graph import GraphNodeV1, GraphSnapshotV1
from aegis_contracts.risk import (
    RiskEngineConfigV1,
    RiskInputV1,
    RiskSignalSourceType,
    RiskSignalStatus,
)
from aegis_contracts.versioning import (
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    RISK_ENGINE_CONFIG_SCHEMA_VERSION,
    RISK_INPUT_SCHEMA_VERSION,
)
from aegis_graph_risk import DEFAULT_RISK_ENGINE_CONFIG_V1, GraphRiskError, compute_risk_scores

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FB1"


def test_missing_origin_asset_fails_closed() -> None:
    snapshot = GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=datetime.now(tz=UTC),
        nodes=[
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:only",
                entity_type="asset",
                asset_type="service",
                label="Only",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.5,
                status="normal",
                revision=1,
            ),
        ],
        edges=[],
        clusters=[],
        revision=1,
    )
    signal = RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-missing",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:missing",
        strength=0.5,
        confidence=0.5,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="missing",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:missing",
    )
    with pytest.raises(GraphRiskError):
        compute_risk_scores(
            snapshot,
            [signal],
            DEFAULT_RISK_ENGINE_CONFIG_V1,
            current_sim_time=datetime.now(tz=UTC),
            computed_at_sequence=2,
        )


def test_incompatible_algorithm_version_rejected() -> None:
    with pytest.raises(ContractValidationError):
        RiskEngineConfigV1(
            schema_version=RISK_ENGINE_CONFIG_SCHEMA_VERSION,
            algorithm_version="graph-risk-v0",
            global_cap=1.0,
            max_hops=4,
            distance_decay_factor=0.65,
            temporal_decay_factor=0.5,
            temporal_half_life_seconds=3600.0,
            criticality_amplifier=0.25,
            min_explanation_contribution=0.01,
            relationship_type_weights=DEFAULT_RISK_ENGINE_CONFIG_V1.relationship_type_weights,
            eligible_relationship_types=DEFAULT_RISK_ENGINE_CONFIG_V1.eligible_relationship_types,
            top_explanation_paths=5,
        )
