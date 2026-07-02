"""Default risk engine configuration."""

from __future__ import annotations

from aegis_contracts.graph import RelationshipType
from aegis_contracts.risk import RiskEngineConfigV1
from aegis_contracts.versioning import RISK_ENGINE_CONFIG_SCHEMA_VERSION

from aegis_graph_risk.version import GRAPH_RISK_ALGORITHM_VERSION

DEFAULT_RISK_ENGINE_CONFIG_V1 = RiskEngineConfigV1(
    schema_version=RISK_ENGINE_CONFIG_SCHEMA_VERSION,
    algorithm_version=GRAPH_RISK_ALGORITHM_VERSION,
    global_cap=1.0,
    max_hops=4,
    distance_decay_factor=0.65,
    temporal_decay_factor=0.5,
    temporal_half_life_seconds=3600.0,
    criticality_amplifier=0.25,
    min_explanation_contribution=0.01,
    relationship_type_weights={item.value: 1.0 for item in RelationshipType},
    eligible_relationship_types=list(RelationshipType),
    top_explanation_paths=5,
)
