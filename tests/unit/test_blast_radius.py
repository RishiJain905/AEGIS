"""Unit tests for the deterministic containment blast-radius projection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts.blast_radius import BlastRadiusImpactKindV1
from aegis_contracts.entities import ActionClass
from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import (
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
)
from aegis_simulation.blast_radius import compute_blast_radius

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _node(asset_id: str, *, label: str, criticality: float, status: str = "normal") -> GraphNodeV1:
    return GraphNodeV1(
        schema_version=GRAPH_NODE_SCHEMA_VERSION,
        id=asset_id,
        entity_type="asset",
        asset_type="service",
        label=label,
        cluster_id="business-unit:test",
        risk_score=0.1,
        criticality=criticality,
        status=status,
        revision=1,
    )


def _edge(edge_id: str, source: str, target: str, relationship_type: str) -> GraphEdgeV1:
    return GraphEdgeV1(
        schema_version=GRAPH_EDGE_SCHEMA_VERSION,
        id=edge_id,
        source=source,
        target=target,
        relationship_type=relationship_type,
        directed=True,
        confidence=1.0,
        risk_contribution=0.2,
        first_seen_at=_NOW,
        last_seen_at=_NOW,
        event_count=1,
        revision=1,
    )


def _snapshot() -> GraphSnapshotV1:
    """A small logistics-shaped graph.

    fleet --DEPENDS_ON--> logistics <--DEPENDS_ON-- route-opt
    logistics --DEPENDS_ON--> comms  (comms is what logistics needs)
    logistics --AUTHENTICATED_TO--> identity
    dispatch --COMMUNICATED_WITH--> logistics
    k8s --HOSTS--> logistics
    """
    nodes = [
        _node("asset:logistics", label="Logistics API", criticality=0.93),
        _node("asset:fleet", label="Fleet Coordinator", criticality=0.85),
        _node("asset:route-opt", label="Route Optimizer", criticality=0.80),
        _node("asset:comms", label="Comms Gateway", criticality=0.90),
        _node("asset:identity", label="Identity Broker", criticality=0.96),
        _node("asset:dispatch", label="Dispatch Terminal", criticality=0.55),
        _node("asset:k8s", label="K8s Control Plane", criticality=0.95),
    ]
    edges = [
        _edge("edge:fleet-logistics", "asset:fleet", "asset:logistics", "DEPENDS_ON"),
        _edge("edge:route-logistics", "asset:route-opt", "asset:logistics", "DEPENDS_ON"),
        _edge("edge:logistics-comms", "asset:logistics", "asset:comms", "DEPENDS_ON"),
        _edge("edge:logistics-identity", "asset:logistics", "asset:identity", "AUTHENTICATED_TO"),
        _edge("edge:dispatch-logistics", "asset:dispatch", "asset:logistics", "COMMUNICATED_WITH"),
        _edge("edge:k8s-logistics", "asset:k8s", "asset:logistics", "HOSTS"),
    ]
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=_NOW,
        nodes=nodes,
        edges=edges,
        clusters=[],
        revision=1,
    )


def _preview(command: ScenarioCommandTemplateV1, target: str = "asset:logistics"):
    return compute_blast_radius(
        _snapshot(), run_id=RUN_ID, command=command, target_asset_id=target
    )


def test_isolate_severs_all_touching_edges() -> None:
    preview = _preview(ScenarioCommandTemplateV1.ISOLATE)
    assert preview.action_class is ActionClass.OPERATIONAL
    # All six edges touch logistics; every one is severed.
    assert preview.severed_edge_count == 6
    assert preview.degraded_edge_count == 0
    assert all(i.impact_kind is BlastRadiusImpactKindV1.SEVERED for i in preview.impacted_assets)
    impacted = {i.asset_id for i in preview.impacted_assets}
    assert impacted == {
        "asset:fleet",
        "asset:route-opt",
        "asset:comms",
        "asset:identity",
        "asset:dispatch",
        "asset:k8s",
    }


def test_isolate_downstream_cascade_reaches_dependents() -> None:
    preview = _preview(ScenarioCommandTemplateV1.ISOLATE)
    downstream = {d.asset_id: d.hops for d in preview.downstream_assets}
    # fleet, route-opt depend on logistics (DEPENDS_ON); k8s HOSTS it — all 1 hop.
    assert downstream["asset:fleet"] == 1
    assert downstream["asset:route-opt"] == 1
    assert downstream["asset:k8s"] == 1
    # comms is what logistics needs (outgoing), not a dependent → not downstream.
    assert "asset:comms" not in downstream


def test_revoke_credentials_degrades_only_auth_edges() -> None:
    preview = _preview(ScenarioCommandTemplateV1.REVOKE_CREDENTIALS)
    assert preview.action_class is ActionClass.OPERATIONAL
    assert preview.severed_edge_count == 0
    # Only the AUTHENTICATED_TO edge to identity degrades.
    assert preview.degraded_edge_count == 1
    assert [i.asset_id for i in preview.impacted_assets] == ["asset:identity"]
    assert preview.impacted_assets[0].impact_kind is BlastRadiusImpactKindV1.DEGRADED
    # No dependency cascade for a credential revoke.
    assert preview.downstream_assets == []


def test_restart_service_outages_only_dependents() -> None:
    preview = _preview(ScenarioCommandTemplateV1.RESTART_SERVICE)
    assert preview.action_class is ActionClass.CRITICAL
    # Dependents of logistics via DEPENDS_ON/HOSTS: fleet, route-opt, k8s.
    impacted = {i.asset_id for i in preview.impacted_assets}
    assert impacted == {"asset:fleet", "asset:route-opt", "asset:k8s"}
    assert all(i.impact_kind is BlastRadiusImpactKindV1.OUTAGE for i in preview.impacted_assets)
    # comms/identity/dispatch are not dependents → untouched.
    assert "asset:comms" not in impacted
    assert "asset:identity" not in impacted


def test_rollback_deployment_degrades_deploy_edges() -> None:
    preview = _preview(ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT)
    assert preview.action_class is ActionClass.CRITICAL
    # HOSTS + DEPENDS_ON edges touching logistics; not the COMMUNICATED_WITH / AUTHENTICATED_TO.
    kinds = {i.asset_id: i.impact_kind for i in preview.impacted_assets}
    assert "asset:k8s" in kinds  # HOSTS
    assert "asset:comms" in kinds  # DEPENDS_ON (outgoing)
    assert "asset:fleet" in kinds  # DEPENDS_ON (incoming)
    assert "asset:dispatch" not in kinds  # COMMUNICATED_WITH excluded
    assert "asset:identity" not in kinds  # AUTHENTICATED_TO excluded


def test_observe_is_read_only() -> None:
    preview = _preview(ScenarioCommandTemplateV1.OBSERVE)
    assert preview.action_class is ActionClass.READ_ONLY
    assert preview.severed_edge_count == 0
    assert preview.degraded_edge_count == 0
    assert preview.impacted_assets == []
    assert preview.downstream_assets == []
    assert preview.warnings  # still explains why nothing happens


def test_missing_target_returns_empty_preview_with_warning() -> None:
    preview = _preview(ScenarioCommandTemplateV1.ISOLATE, target="asset:does-not-exist")
    assert preview.severed_edge_count == 0
    assert preview.impacted_assets == []
    assert preview.downstream_assets == []
    assert any("not present" in w for w in preview.warnings)


def test_high_criticality_asset_is_called_out() -> None:
    preview = _preview(ScenarioCommandTemplateV1.ISOLATE)
    # identity (0.96), logistics-neighbours comms (0.90), k8s (0.95) are >= 0.9.
    assert any("high-criticality" in w.lower() for w in preview.warnings)


def test_isolated_leaf_node_has_no_collateral() -> None:
    # A node with a single COMMUNICATED_WITH edge: isolate severs one edge, no cascade.
    preview = _preview(ScenarioCommandTemplateV1.ISOLATE, target="asset:dispatch")
    assert preview.severed_edge_count == 1
    assert [i.asset_id for i in preview.impacted_assets] == ["asset:logistics"]
    assert preview.downstream_assets == []


def test_deterministic_output() -> None:
    a = _preview(ScenarioCommandTemplateV1.ISOLATE)
    b = _preview(ScenarioCommandTemplateV1.ISOLATE)
    assert a.model_dump(by_alias=True) == b.model_dump(by_alias=True)


@pytest.mark.parametrize(
    "command",
    list(ScenarioCommandTemplateV1),
)
def test_every_command_produces_a_valid_preview(command: ScenarioCommandTemplateV1) -> None:
    preview = _preview(command)
    assert preview.run_id == RUN_ID
    assert preview.command is command
    assert preview.severed_edge_count >= 0
    assert preview.degraded_edge_count >= 0
