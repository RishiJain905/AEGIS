"""Graph snapshot indexing for propagation."""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1, RelationshipType

from aegis_graph_risk.errors import GraphRiskError, GraphRiskErrorCode


@dataclass(slots=True)
class IndexedEdge:
    edge: GraphEdgeV1
    weight: float


@dataclass(slots=True)
class GraphIndex:
    nodes: dict[str, GraphNodeV1]
    outgoing: dict[str, list[IndexedEdge]] = field(default_factory=dict)
    incoming: dict[str, list[IndexedEdge]] = field(default_factory=dict)

    def neighbors(self, node_id: str) -> list[tuple[str, IndexedEdge]]:
        return [(indexed.edge.target, indexed) for indexed in self.outgoing.get(node_id, [])]


def build_graph_index(
    snapshot: GraphSnapshotV1,
    *,
    eligible_types: set[RelationshipType],
    relationship_type_weights: dict[str, float],
) -> GraphIndex:
    nodes = {node.id: node for node in snapshot.nodes}
    outgoing: dict[str, list[IndexedEdge]] = {node_id: [] for node_id in nodes}
    incoming: dict[str, list[IndexedEdge]] = {node_id: [] for node_id in nodes}

    for edge in sorted(snapshot.edges, key=lambda item: item.id):
        if edge.source not in nodes or edge.target not in nodes:
            continue
        if edge.relationship_type not in eligible_types:
            continue
        type_weight = relationship_type_weights.get(edge.relationship_type.value, 1.0)
        if type_weight < 0.0 or type_weight > 1.0:
            raise GraphRiskError(
                code=GraphRiskErrorCode.INVALID_WEIGHT,
                message=f"Invalid relationship type weight for {edge.relationship_type.value}",
                details={"relationshipType": edge.relationship_type.value, "weight": type_weight},
            )
        edge_weight = edge.risk_contribution * edge.confidence * type_weight
        if edge_weight < 0.0 or edge_weight > 1.0:
            raise GraphRiskError(
                code=GraphRiskErrorCode.INVALID_WEIGHT,
                message=f"Computed edge weight out of bounds for {edge.id}",
                details={"edgeId": edge.id, "weight": edge_weight},
            )
        indexed = IndexedEdge(edge=edge, weight=edge_weight)
        outgoing[edge.source].append(indexed)
        incoming[edge.target].append(indexed)
        if not edge.directed:
            reverse = IndexedEdge(
                edge=GraphEdgeV1(
                    schema_version=edge.schema_version,
                    id=f"{edge.id}:reverse",
                    source=edge.target,
                    target=edge.source,
                    relationship_type=edge.relationship_type,
                    directed=False,
                    confidence=edge.confidence,
                    risk_contribution=edge.risk_contribution,
                    first_seen_at=edge.first_seen_at,
                    last_seen_at=edge.last_seen_at,
                    event_count=edge.event_count,
                    revision=edge.revision,
                ),
                weight=edge_weight,
            )
            outgoing[edge.target].append(reverse)
            incoming[edge.source].append(reverse)

    for node_id in outgoing:
        outgoing[node_id].sort(key=lambda item: (item.edge.id, item.edge.target))
    for node_id in incoming:
        incoming[node_id].sort(key=lambda item: (item.edge.id, item.edge.source))

    return GraphIndex(nodes=nodes, outgoing=outgoing, incoming=incoming)


def validate_snapshot_entities(snapshot: GraphSnapshotV1, asset_ids: set[str]) -> None:
    node_ids = {node.id for node in snapshot.nodes}
    missing = sorted(asset_id for asset_id in asset_ids if asset_id not in node_ids)
    if missing:
        raise GraphRiskError(
            code=GraphRiskErrorCode.MISSING_ENTITY,
            message="Risk signal references assets missing from graph snapshot",
            details={"missingAssetIds": missing},
        )
