"""Fog-of-war disclosure model, snapshot redaction, and threat-tempo unit tests.

Offline — no DB, no infra. Uses the real synthetic-training manifest (two hidden
conditions, three attacker-governed assets) so the governing-map resolution is exercised
against a shipped scenario rather than a hand-rolled fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from aegis_contracts import GraphSnapshotV1
from aegis_simulation_domain import (
    REDACTED_STATUS,
    DisclosureInputs,
    SimulationEngine,
    ThreatTempoState,
    TriggeredCondition,
    build_governing_map,
    compute_threat_tempo,
    disclosure_inputs_from_events,
    is_asset_disclosed,
    redact_graph_snapshot,
)

_ROOT = Path(__file__).resolve().parents[2]
_TRAINING_PACKAGE = _ROOT / "scenarios" / "synthetic-training"

_WORKSTATION = "asset:device-workstation-alpha"
_FILE_SERVER = "asset:svc-file-server"
_RECORDS_DB = "asset:database-student-records"
_IDP = "asset:svc-identity-provider"  # telemetry only → ungoverned

_PHISH = "hidden-cause-phishing-compromise"
_EXFIL = "hidden-cause-data-exfiltration"


@pytest.fixture(scope="module")
def manifest():
    return SimulationEngine.load_manifest(_TRAINING_PACKAGE)


@pytest.fixture(scope="module")
def governing_map(manifest):
    return build_governing_map(manifest)


def test_governing_map_links_effects_to_assets(governing_map):
    assert set(governing_map) == {_WORKSTATION, _FILE_SERVER, _RECORDS_DB}
    assert governing_map[_WORKSTATION].condition_ids == frozenset({_PHISH})
    assert governing_map[_FILE_SERVER].condition_ids == frozenset({_PHISH})
    assert governing_map[_RECORDS_DB].condition_ids == frozenset({_EXFIL})
    # Ungoverned assets never appear in the map.
    assert _IDP not in governing_map


def test_ungoverned_asset_always_disclosed(governing_map):
    assert is_asset_disclosed(_IDP, governing_map, DisclosureInputs()) is True
    # Even an unknown/never-seen asset id is disclosed (nothing hides it).
    assert is_asset_disclosed("asset:whatever", governing_map, DisclosureInputs()) is True


def test_governed_asset_hidden_until_reveal(governing_map):
    assert is_asset_disclosed(_WORKSTATION, governing_map, DisclosureInputs()) is False
    revealed = DisclosureInputs(revealed_condition_ids=frozenset({_PHISH}))
    assert is_asset_disclosed(_WORKSTATION, governing_map, revealed) is True
    # Revealing the phishing condition does not disclose the exfil-governed asset.
    assert is_asset_disclosed(_RECORDS_DB, governing_map, revealed) is False


def test_governed_asset_disclosed_by_alert(governing_map):
    alerted = DisclosureInputs(alerted_asset_ids=frozenset({_FILE_SERVER}))
    assert is_asset_disclosed(_FILE_SERVER, governing_map, alerted) is True
    # Alerting the file server does not disclose the sibling workstation.
    assert is_asset_disclosed(_WORKSTATION, governing_map, alerted) is False


def _snapshot(
    *,
    status: str,
    risk: float,
    asset_id: str = _WORKSTATION,
    applied_controls: list[str] | None = None,
) -> GraphSnapshotV1:
    return GraphSnapshotV1.model_validate(
        {
            "schemaVersion": 1,
            "runId": "run_" + "A" * 26,
            "sequence": 7,
            "capturedAt": "2026-01-01T00:00:00.000Z",
            "nodes": [
                {
                    "schemaVersion": 1,
                    "id": asset_id,
                    "entityType": "asset",
                    "assetType": "device",
                    "label": "WS",
                    "appliedControls": applied_controls or [],
                    "riskScore": risk,
                    "criticality": 0.5,
                    "status": status,
                    "revision": 4,
                }
            ],
            "edges": [],
            "clusters": [],
            "revision": 4,
        }
    )


def test_redaction_hides_undisclosed_attacker_state(governing_map):
    snap = _snapshot(status="compromised", risk=0.9)
    redacted = redact_graph_snapshot(snap, governing_map, DisclosureInputs())
    node = redacted.nodes[0]
    assert node.status == REDACTED_STATUS
    assert node.disclosed is False
    # Attacker-driven risk spike is soft-pedalled to the manifest baseline.
    assert node.risk_score <= governing_map[_WORKSTATION].baseline_risk


def test_redaction_reveals_true_state_after_disclosure(governing_map):
    snap = _snapshot(status="compromised", risk=0.9)
    inputs = DisclosureInputs(revealed_condition_ids=frozenset({_PHISH}))
    redacted = redact_graph_snapshot(snap, governing_map, inputs)
    node = redacted.nodes[0]
    assert node.status == "compromised"
    assert node.disclosed is True
    assert node.risk_score == pytest.approx(0.9)


def test_redaction_keeps_the_operators_own_controls_on_a_fogged_asset(governing_map):
    """Fog hides the attacker's work, never the operator's.

    Containing a still-fogged asset used to come back reading ``normal``: the redaction
    blanked the whole composed status, so the operator's own isolate order vanished from
    the graph they were watching. The posture underneath stays hidden; the control does
    not.
    """
    snap = _snapshot(status="contained", risk=0.9, applied_controls=["isolated"])
    redacted = redact_graph_snapshot(snap, governing_map, DisclosureInputs())
    node = redacted.nodes[0]
    assert node.status == "contained"
    assert node.applied_controls == ["isolated"]
    assert node.disclosed is False
    # The compromise underneath is still hidden — the risk spike does not leak.
    assert node.risk_score <= governing_map[_WORKSTATION].baseline_risk


def test_redaction_of_an_observed_fogged_asset_reads_under_investigation(governing_map):
    """An observation control is not containment, so it composes over the *baseline*.

    The compromise it is sitting on top of stays hidden, which is the whole point: the
    operator learns they are watching the asset, not that they were right to.
    """
    snap = _snapshot(status="compromised", risk=0.9, applied_controls=["observed"])
    redacted = redact_graph_snapshot(snap, governing_map, DisclosureInputs())
    node = redacted.nodes[0]
    assert node.status == "under_investigation"
    assert node.applied_controls == ["observed"]
    assert node.disclosed is False


def test_redaction_leaves_ungoverned_untouched(governing_map):
    snap = _snapshot(status="suspicious", risk=0.7, asset_id=_IDP)
    redacted = redact_graph_snapshot(snap, governing_map, DisclosureInputs())
    node = redacted.nodes[0]
    assert node.status == "suspicious"
    assert node.disclosed is True


def test_disclosure_inputs_from_events():
    def event(event_type: str, payload: dict) -> object:
        class _E:
            type = event_type

        e = _E()
        e.payload = payload  # type: ignore[attr-defined]
        return e

    events = [
        event("sim.hidden_condition.revealed", {"conditionId": _PHISH}),
        event("alert.created", {"assetId": _RECORDS_DB, "title": "x"}),
        event("telemetry.authentication.failed", {"assetId": _IDP}),
    ]
    inputs = disclosure_inputs_from_events(events)
    assert inputs.revealed_condition_ids == frozenset({_PHISH})
    assert inputs.alerted_asset_ids == frozenset({_RECORDS_DB})


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def test_threat_tempo_zero_without_triggers():
    state = ThreatTempoState(current_sim_time=_now(), triggered=[], total_conditions=2)
    assert compute_threat_tempo(state, saturation_sim_seconds=600.0) == 0.0


def test_threat_tempo_ramps_with_dwell_time():
    now = _now()
    early = ThreatTempoState(
        current_sim_time=now,
        triggered=[TriggeredCondition(_PHISH, now - timedelta(seconds=60))],
        total_conditions=2,
    )
    late = ThreatTempoState(
        current_sim_time=now,
        triggered=[TriggeredCondition(_PHISH, now - timedelta(seconds=600))],
        total_conditions=2,
    )
    tempo_early = compute_threat_tempo(early, saturation_sim_seconds=600.0)
    tempo_late = compute_threat_tempo(late, saturation_sim_seconds=600.0)
    assert 0.0 < tempo_early < tempo_late
    # One of two conditions fully saturated → half of the normalised ceiling.
    assert tempo_late == pytest.approx(0.5)


def test_threat_tempo_relieved_by_disclosure():
    now = _now()
    triggered = [TriggeredCondition(_PHISH, now - timedelta(seconds=600))]
    pressured = ThreatTempoState(
        current_sim_time=now, triggered=triggered, total_conditions=2
    )
    disclosed = ThreatTempoState(
        current_sim_time=now,
        triggered=triggered,
        revealed_condition_ids=frozenset({_PHISH}),
        total_conditions=2,
    )
    assert compute_threat_tempo(pressured, saturation_sim_seconds=600.0) > 0.0
    assert compute_threat_tempo(disclosed, saturation_sim_seconds=600.0) == 0.0
