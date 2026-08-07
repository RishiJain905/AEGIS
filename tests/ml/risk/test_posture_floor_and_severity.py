"""The risk engine reads posture, and an alert's strength comes from its severity.

Two defects behind the inert RISK SCORE, on the engine side rather than the projection:

1. ``compute_risk_scores`` only ever saw detection signals. A compromised asset with no
   detector firing on it scored zero, so posture — the most load-bearing fact about an
   asset — could not move the number the engine produced.
2. ``normalize_alert_to_risk_input`` set *both* ``strength`` and ``confidence`` to
   ``alert.confidence``, and the engine multiplies the two. Every alert's contribution was
   therefore its confidence *squared* (0.75 confidence -> 0.5625), and severity was
   discarded entirely: a critical alert and an informational one at equal confidence
   contributed identically.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts.entities import AlertV1
from aegis_contracts.graph import GraphNodeV1, GraphSnapshotV1, NodeStatus
from aegis_contracts.versioning import (
    ALERT_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
)
from aegis_graph_risk import DEFAULT_RISK_ENGINE_CONFIG_V1, compute_risk_scores
from aegis_graph_risk.normalize import normalize_alert_to_risk_input
from aegis_graph_risk.posture import posture_risk

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAX"
NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _node(asset_id: str, status: str, criticality: float, risk: float = 0.1) -> GraphNodeV1:
    return GraphNodeV1(
        schema_version=GRAPH_NODE_SCHEMA_VERSION,
        id=asset_id,
        entity_type="asset",
        asset_type="service",
        label=asset_id,
        cluster_id="business-unit:bu",
        risk_score=risk,
        criticality=criticality,
        status=status,
        revision=1,
    )


def _snapshot(*nodes: GraphNodeV1) -> GraphSnapshotV1:
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=NOW,
        nodes=list(nodes),
        edges=[],
        clusters=[],
        revision=1,
    )


def _scores(snapshot: GraphSnapshotV1) -> dict[str, float]:
    result = compute_risk_scores(
        snapshot,
        [],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=NOW,
        computed_at_sequence=2,
    )
    return {score.asset_id: score.total for score in result.scores}


def test_compromised_asset_outranks_a_normal_one_with_no_detections_at_all() -> None:
    totals = _scores(
        _snapshot(
            _node("asset:owned", NodeStatus.COMPROMISED.value, 0.5),
            _node("asset:quiet", NodeStatus.NORMAL.value, 0.95),
        )
    )
    assert totals["asset:owned"] > totals["asset:quiet"]


def test_containment_lowers_the_engine_total_from_the_compromised_peak() -> None:
    peak = _scores(_snapshot(_node("asset:a", NodeStatus.COMPROMISED.value, 0.9)))["asset:a"]
    contained = _scores(_snapshot(_node("asset:a", NodeStatus.CONTAINED.value, 0.9)))["asset:a"]
    at_rest = _scores(_snapshot(_node("asset:a", NodeStatus.NORMAL.value, 0.9)))["asset:a"]
    assert at_rest < contained < peak


def test_posture_enters_as_direct_risk_originating_at_the_asset() -> None:
    result = compute_risk_scores(
        _snapshot(_node("asset:a", NodeStatus.COMPROMISED.value, 0.9)),
        [],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=NOW,
        computed_at_sequence=2,
    )
    score = next(item for item in result.scores if item.asset_id == "asset:a")
    assert score.direct == pytest.approx(posture_risk(NodeStatus.COMPROMISED.value, 0.9))
    assert score.propagated == 0.0
    assert score.total == pytest.approx(score.direct)


def test_evidence_still_raises_a_score_above_its_posture_floor() -> None:
    node = _node("asset:a", NodeStatus.NORMAL.value, 0.4)
    floor = posture_risk(NodeStatus.NORMAL.value, 0.4, authored_floor=node.risk_score)
    alert_input = normalize_alert_to_risk_input(_alert(severity="critical"), sim_time=NOW)
    result = compute_risk_scores(
        _snapshot(node),
        [alert_input],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=NOW,
        computed_at_sequence=2,
    )
    score = next(item for item in result.scores if item.asset_id == "asset:a")
    assert score.total > floor


def test_engine_total_never_reports_less_risk_than_the_graph_already_shows() -> None:
    node = _node("asset:a", NodeStatus.NORMAL.value, 0.1, risk=0.62)
    assert _scores(_snapshot(node))["asset:a"] >= 0.62


def _alert(*, severity: str, confidence: float | None = 0.75) -> AlertV1:
    return AlertV1(
        schema_version=ALERT_SCHEMA_VERSION,
        id="alert:sev",
        run_id=RUN_ID,
        title="Test alert",
        severity=severity,
        source_event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        asset_id="asset:a",
        created_at=NOW,
        confidence=confidence,
    )


def test_severity_drives_strength_and_confidence_is_no_longer_squared() -> None:
    critical = normalize_alert_to_risk_input(_alert(severity="critical"), sim_time=NOW)
    low = normalize_alert_to_risk_input(_alert(severity="low"), sim_time=NOW)

    assert critical.strength > low.strength
    assert critical.confidence == pytest.approx(0.75)
    assert low.confidence == pytest.approx(0.75)
    # The old behaviour: strength == confidence, so both alerts normalized identically.
    assert critical.strength != critical.confidence


def test_severity_ladder_is_monotonic() -> None:
    ladder = ["informational", "info", "low", "medium", "high", "critical"]
    strengths = [
        normalize_alert_to_risk_input(_alert(severity=name), sim_time=NOW).strength
        for name in ladder
    ]
    assert strengths == sorted(strengths)
    assert strengths[-1] > strengths[0]


def test_severity_is_matched_case_insensitively() -> None:
    upper = normalize_alert_to_risk_input(_alert(severity="CRITICAL"), sim_time=NOW)
    lower = normalize_alert_to_risk_input(_alert(severity="critical"), sim_time=NOW)
    assert upper.strength == lower.strength


def test_unknown_severity_falls_back_without_raising() -> None:
    unknown = normalize_alert_to_risk_input(_alert(severity="catastrophic"), sim_time=NOW)
    assert 0.0 < unknown.strength <= 1.0


def test_missing_confidence_does_not_zero_the_signal() -> None:
    absent = normalize_alert_to_risk_input(_alert(severity="high", confidence=None), sim_time=NOW)
    assert absent.confidence > 0.0
    assert absent.strength > 0.0
