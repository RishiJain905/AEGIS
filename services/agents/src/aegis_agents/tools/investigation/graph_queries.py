"""Graph snapshot query helpers for investigation read tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1, RelationshipType


def _edge_passes_filter(
    edge: GraphEdgeV1,
    *,
    relationship_types: list[str] | None,
    directed_only: bool,
) -> bool:
    if relationship_types and edge.relationship_type.value not in relationship_types:
        return False
    return not (directed_only and not edge.directed)

def get_asset_from_snapshot(snapshot: GraphSnapshotV1, asset_id: str) -> GraphNodeV1 | None:
    for node in snapshot.nodes:
        if node.id == asset_id:
            return node
    return None


@dataclass
class NeighborhoodResult:
    center_node_id: str
    max_degree: int
    node_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    hop_rings: list[list[str]] = field(default_factory=list)
    explanation: dict[str, Any] = field(default_factory=dict)


def get_relationships_on_snapshot(
    snapshot: GraphSnapshotV1,
    asset_id: str,
    *,
    max_degree: int = 8,
    relationship_types: list[str] | None = None,
    directed_only: bool = False,
) -> NeighborhoodResult:
    nodes_by_id = {node.id: node for node in snapshot.nodes}
    if asset_id not in nodes_by_id:
        msg = f"Asset not found in graph snapshot: {asset_id}"
        raise KeyError(msg)

    outgoing: dict[str, list[GraphEdgeV1]] = {node_id: [] for node_id in nodes_by_id}
    incoming: dict[str, list[GraphEdgeV1]] = {node_id: [] for node_id in nodes_by_id}
    for edge in sorted(snapshot.edges, key=lambda item: item.id):
        if edge.source not in nodes_by_id or edge.target not in nodes_by_id:
            continue
        outgoing[edge.source].append(edge)
        incoming[edge.target].append(edge)
        if not edge.directed:
            outgoing[edge.target].append(edge)
            incoming[edge.source].append(edge)

    node_ids: set[str] = {asset_id}
    edge_ids: set[str] = set()
    hop_rings: list[list[str]] = []
    frontier = {asset_id}
    visited = {asset_id}

    for _hop in range(1, max_degree + 1):
        ring: list[str] = []
        next_frontier: set[str] = set()
        for current in sorted(frontier):
            for edge in outgoing[current]:
                if not _edge_passes_filter(
                    edge,
                    relationship_types=relationship_types,
                    directed_only=directed_only,
                ):
                    continue
                target = edge.target
                edge_ids.add(edge.id)
                if target not in visited:
                    visited.add(target)
                    node_ids.add(target)
                    ring.append(target)
                    next_frontier.add(target)
            if not directed_only:
                for edge in incoming[current]:
                    if not _edge_passes_filter(
                        edge,
                        relationship_types=relationship_types,
                        directed_only=directed_only,
                    ):
                        continue
                    source = edge.source
                    edge_ids.add(edge.id)
                    if source not in visited:
                        visited.add(source)
                        node_ids.add(source)
                        ring.append(source)
                        next_frontier.add(source)
        ring.sort()
        hop_rings.append(ring)
        frontier = next_frontier
        if not frontier:
            break

    return NeighborhoodResult(
        center_node_id=asset_id,
        max_degree=max_degree,
        node_ids=sorted(node_ids),
        edge_ids=sorted(edge_ids),
        hop_rings=hop_rings,
        explanation={
            "nodesReached": len(node_ids),
            "edgesIncluded": len(edge_ids),
            "relationshipTypes": relationship_types or [],
            "directedOnly": directed_only,
        },
    )


def query_paths_on_snapshot(
    snapshot: GraphSnapshotV1,
    *,
    source_id: str,
    target_id: str,
    max_hops: int = 4,
    relationship_types: list[str] | None = None,
    directed_only: bool = True,
) -> dict[str, Any]:
    nodes_by_id = {node.id: node for node in snapshot.nodes}
    if source_id not in nodes_by_id or target_id not in nodes_by_id:
        return {
            "sourceId": source_id,
            "targetId": target_id,
            "paths": [],
            "explanation": {
                "hopCount": 0,
                "pathsConsidered": 0,
                "reason": "source_or_target_not_found",
            },
        }

    if source_id == target_id:
        return {
            "sourceId": source_id,
            "targetId": target_id,
            "paths": [[source_id]],
            "explanation": {
                "hopCount": 0,
                "pathsConsidered": 1,
                "relationshipTypes": relationship_types or [],
            },
        }

    outgoing: dict[str, list[GraphEdgeV1]] = {node_id: [] for node_id in nodes_by_id}
    incoming: dict[str, list[GraphEdgeV1]] = {node_id: [] for node_id in nodes_by_id}
    for edge in sorted(snapshot.edges, key=lambda item: item.id):
        if edge.source not in nodes_by_id or edge.target not in nodes_by_id:
            continue
        outgoing[edge.source].append(edge)
        incoming[edge.target].append(edge)

    paths: list[list[str]] = []
    paths_considered = 0
    queue: list[tuple[list[str], set[str]]] = [([source_id], {source_id})]

    while queue:
        path, visited = queue.pop(0)
        last_node = path[-1]
        if len(path) - 1 >= max_hops:
            continue

        for edge in outgoing[last_node]:
            paths_considered += 1
            if not _edge_passes_filter(
                edge,
                relationship_types=relationship_types,
                directed_only=directed_only,
            ):
                continue
            next_node = edge.target
            next_path = [*path, next_node]
            if next_node == target_id:
                paths.append(next_path)
                continue
            if next_node not in visited and len(next_path) - 1 <= max_hops:
                next_visited = set(visited)
                next_visited.add(next_node)
                queue.append((next_path, next_visited))

        if not directed_only:
            for edge in incoming[last_node]:
                paths_considered += 1
                if not _edge_passes_filter(
                    edge,
                    relationship_types=relationship_types,
                    directed_only=directed_only,
                ):
                    continue
                next_node = edge.source
                if next_node in visited:
                    continue
                next_path = [*path, next_node]
                if next_node == target_id:
                    paths.append(next_path)
                    continue
                if len(next_path) - 1 <= max_hops:
                    next_visited = set(visited)
                    next_visited.add(next_node)
                    queue.append((next_path, next_visited))

    paths.sort(key=lambda item: (len(item), item))
    shortest_hop_count = len(paths[0]) - 1 if paths else 0
    return {
        "sourceId": source_id,
        "targetId": target_id,
        "paths": paths,
        "explanation": {
            "hopCount": shortest_hop_count,
            "pathsConsidered": paths_considered,
            "pathsFound": len(paths),
            "relationshipTypes": relationship_types
            or [item.value for item in RelationshipType],
            "directedOnly": directed_only,
            "ordering": "lexicographic_by_node_id",
        },
    }
