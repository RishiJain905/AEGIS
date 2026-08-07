"""Deterministic graph risk propagation engine."""

from aegis_graph_risk.config import DEFAULT_RISK_ENGINE_CONFIG_V1
from aegis_graph_risk.errors import GraphRiskError, GraphRiskErrorCode
from aegis_graph_risk.incremental import recompute_incremental
from aegis_graph_risk.normalize import (
    ALERT_SEVERITY_STRENGTH,
    alert_severity_strength,
    deduplicate_risk_inputs,
    normalize_alert_to_risk_input,
    normalize_model_score_to_risk_input,
)
from aegis_graph_risk.posture import (
    POSTURE_RISK_FLOOR,
    POSTURE_RISK_HEADROOM,
    posture_risk,
)
from aegis_graph_risk.propagate import RiskPropagationResult, compute_risk_scores
from aegis_graph_risk.version import GRAPH_RISK_ALGORITHM_VERSION

__all__ = [
    "ALERT_SEVERITY_STRENGTH",
    "DEFAULT_RISK_ENGINE_CONFIG_V1",
    "GRAPH_RISK_ALGORITHM_VERSION",
    "POSTURE_RISK_FLOOR",
    "POSTURE_RISK_HEADROOM",
    "GraphRiskError",
    "GraphRiskErrorCode",
    "RiskPropagationResult",
    "alert_severity_strength",
    "compute_risk_scores",
    "deduplicate_risk_inputs",
    "normalize_alert_to_risk_input",
    "normalize_model_score_to_risk_input",
    "posture_risk",
    "recompute_incremental",
]
