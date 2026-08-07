"""Posture-derived risk gives the score real dynamic range across a run.

The defect these cover: ``GraphNodeV1.risk_score`` used to be the scenario's authored
``initial_risk_score``, frozen at seed. Across a whole run every asset stayed inside
0.00-0.20 and a compromised database read lower than an untouched laptop.
"""

from __future__ import annotations

import pytest
from aegis_contracts.graph import NodeStatus
from aegis_graph_risk.posture import POSTURE_RISK_FLOOR, POSTURE_RISK_HEADROOM, posture_risk

CRITICALITIES = [0.0, 0.35, 0.6, 0.94, 1.0]


def test_compromised_outranks_every_non_compromised_asset() -> None:
    """The headline requirement: compromise dominates, whatever the criticality."""
    worst_compromised = min(posture_risk(NodeStatus.COMPROMISED.value, c) for c in CRITICALITIES)
    best_of_the_rest = max(
        posture_risk(status.value, c)
        for status in NodeStatus
        if status is not NodeStatus.COMPROMISED
        for c in CRITICALITIES
    )
    assert worst_compromised > best_of_the_rest


def test_containment_reduces_risk_from_the_compromised_peak_without_clearing_it() -> None:
    criticality = 0.94
    peak = posture_risk(NodeStatus.COMPROMISED.value, criticality)
    contained = posture_risk(NodeStatus.CONTAINED.value, criticality)
    at_rest = posture_risk(NodeStatus.NORMAL.value, criticality)

    assert contained < peak
    assert contained > at_rest


def test_posture_bands_are_strictly_ordered_at_equal_criticality() -> None:
    criticality = 0.8
    ordered = [
        NodeStatus.NORMAL,
        NodeStatus.UNDER_INVESTIGATION,
        NodeStatus.CONTAINED,
        NodeStatus.SUSPICIOUS,
        NodeStatus.COMPROMISED,
    ]
    scores = [posture_risk(status.value, criticality) for status in ordered]
    assert scores == sorted(scores)
    assert len(set(scores)) == len(scores)


def test_criticality_ranks_assets_within_a_posture() -> None:
    low = posture_risk(NodeStatus.SUSPICIOUS.value, 0.2)
    high = posture_risk(NodeStatus.SUSPICIOUS.value, 0.95)
    assert high > low


def test_live_run_spread_is_wider_than_the_frozen_seed_band() -> None:
    """The observed defect was a ~0.20 total spread. Posture has to beat that decisively."""
    observed = [
        posture_risk(status.value, criticality)
        for status in NodeStatus
        for criticality in CRITICALITIES
    ]
    assert max(observed) - min(observed) > 0.8


def test_authored_baseline_is_a_floor_and_never_a_ceiling() -> None:
    # A quiet vendor laptop authored at 0.20 keeps its authored exposure.
    assert posture_risk(NodeStatus.NORMAL.value, 0.6, authored_floor=0.2) == pytest.approx(0.2)
    # Compromise is never pulled back down to the authored baseline.
    compromised = posture_risk(NodeStatus.COMPROMISED.value, 0.6, authored_floor=0.2)
    assert compromised == pytest.approx(
        POSTURE_RISK_FLOOR[NodeStatus.COMPROMISED.value]
        + POSTURE_RISK_HEADROOM[NodeStatus.COMPROMISED.value] * 0.6
    )


def test_every_node_status_has_a_band() -> None:
    for status in NodeStatus:
        assert status.value in POSTURE_RISK_FLOOR
        assert status.value in POSTURE_RISK_HEADROOM


def test_output_is_bounded_and_total() -> None:
    for status in [*[s.value for s in NodeStatus], "not-a-status"]:
        for criticality in [-1.0, 0.0, 0.5, 1.0, 2.0]:
            score = posture_risk(status, criticality, authored_floor=5.0)
            assert 0.0 <= score <= 1.0


def test_unknown_status_bands_as_under_investigation() -> None:
    assert posture_risk("not-a-status", 0.7) == pytest.approx(
        posture_risk(NodeStatus.UNDER_INVESTIGATION.value, 0.7)
    )


def test_is_deterministic() -> None:
    first = [posture_risk(s.value, 0.73, authored_floor=0.11) for s in NodeStatus]
    second = [posture_risk(s.value, 0.73, authored_floor=0.11) for s in NodeStatus]
    assert first == second
