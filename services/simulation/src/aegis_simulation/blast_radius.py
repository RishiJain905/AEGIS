"""Deterministic containment blast-radius computation.

Pure graph traversal over a run's current graph snapshot: given a containment command and a
target asset, project the collateral the operator/approver should see before committing. No
LLM, no persistence, no randomness — same snapshot + (command, target) always yields the same
preview, so it is safe to call on every dialog open.

Command → impact semantics (mirrors the operator's mental model of each action):

* ``ISOLATE`` severs every edge touching the target (full network cut) and cascades an outage
  down the dependency chain.
* ``RESTRICT_ACCESS`` / ``REVOKE_CREDENTIALS`` degrade the identity/auth edges (AUTHENTICATED_TO,
  ADMINISTERS) touching the target — authenticated callers lose their path.
* ``RESTART_SERVICE`` briefly takes the target offline: its direct dependents (who DEPENDS_ON /
  are HOSTED by it) see an outage, cascading transitively.
* ``ROLLBACK_DEPLOYMENT`` disturbs the deployment/hosting edges (HOSTS, ADMINISTERS, DEPENDS_ON)
  around the target.
* ``OBSERVE`` / ``INCREASE_MONITORING`` are read-only: no edges severed or degraded.
"""

from __future__ import annotations

from collections import deque
from enum import StrEnum

from aegis_contracts.blast_radius import (
    BlastRadiusDownstreamV1,
    BlastRadiusImpactKindV1,
    BlastRadiusImpactV1,
    BlastRadiusPreviewV1,
)
from aegis_contracts.entities import ActionClass
from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1, RelationshipType
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import BLAST_RADIUS_PREVIEW_SCHEMA_VERSION

# Command → policy action class, mirroring aegis_policy.commands.COMMAND_TO_ACTION_CLASS.
# Inlined (not imported) to keep the simulation service free of a policy dependency for a
# pure, read-only projection.
_COMMAND_ACTION_CLASS: dict[ScenarioCommandTemplateV1, ActionClass] = {
    ScenarioCommandTemplateV1.OBSERVE: ActionClass.READ_ONLY,
    ScenarioCommandTemplateV1.INCREASE_MONITORING: ActionClass.LOW_IMPACT,
    ScenarioCommandTemplateV1.ISOLATE: ActionClass.OPERATIONAL,
    ScenarioCommandTemplateV1.RESTRICT_ACCESS: ActionClass.OPERATIONAL,
    ScenarioCommandTemplateV1.REVOKE_CREDENTIALS: ActionClass.OPERATIONAL,
    ScenarioCommandTemplateV1.RESTART_SERVICE: ActionClass.CRITICAL,
    ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT: ActionClass.CRITICAL,
}

# Identity/authentication edges degraded by RESTRICT_ACCESS / REVOKE_CREDENTIALS.
_AUTH_RELATIONSHIPS = frozenset(
    {RelationshipType.AUTHENTICATED_TO, RelationshipType.ADMINISTERS}
)
# Deployment/hosting edges disturbed by ROLLBACK_DEPLOYMENT.
_DEPLOY_RELATIONSHIPS = frozenset(
    {RelationshipType.HOSTS, RelationshipType.ADMINISTERS, RelationshipType.DEPENDS_ON}
)
# "X needs Y" edges used to cascade an outage from a downed asset to its dependents.
_DEPENDENCY_RELATIONSHIPS = frozenset(
    {RelationshipType.DEPENDS_ON, RelationshipType.HOSTS}
)
# Commands that take the target offline (drive the transitive dependency cascade).
_OUTAGE_COMMANDS = frozenset(
    {ScenarioCommandTemplateV1.ISOLATE, ScenarioCommandTemplateV1.RESTART_SERVICE}
)

_MAX_CASCADE_DEPTH = 4
_HIGH_CRITICALITY = 0.9


def _as_str(value: object) -> str:
    """Enum-or-str → wire string. Persisted snapshots surface enums as plain strings; a
    freshly-built one carries StrEnum members. ``str()`` yields the value for both."""
    return value.value if isinstance(value, StrEnum) else str(value)


def compute_blast_radius(
    snapshot: GraphSnapshotV1,
    *,
    run_id: str,
    command: ScenarioCommandTemplateV1,
    target_asset_id: str,
) -> BlastRadiusPreviewV1:
    """Project the collateral of ``command`` against ``target_asset_id`` over ``snapshot``.

    Returns a fully-populated :class:`BlastRadiusPreviewV1`. If the target is absent from the
    snapshot (e.g. redacted by fog-of-war, or a stale selection) the preview is empty with an
    explanatory warning rather than raising — the confirm dialog must still open.
    """
    action_class = _COMMAND_ACTION_CLASS[command]
    nodes_by_id = {node.id: node for node in snapshot.nodes}
    target = nodes_by_id.get(target_asset_id)

    if target is None:
        return BlastRadiusPreviewV1(
            schema_version=BLAST_RADIUS_PREVIEW_SCHEMA_VERSION,
            run_id=run_id,
            command=command,
            target_asset_id=target_asset_id,
            action_class=action_class,
            severed_edge_count=0,
            degraded_edge_count=0,
            impacted_assets=[],
            downstream_assets=[],
            warnings=[
                "Target asset is not present in the current graph; no collateral computed."
            ],
        )

    impacts = _direct_impacts(
        snapshot.edges, nodes_by_id, command=command, target_id=target_asset_id
    )
    severed = sum(1 for i in impacts if i.impact_kind is BlastRadiusImpactKindV1.SEVERED)
    degraded = sum(1 for i in impacts if i.impact_kind is not BlastRadiusImpactKindV1.SEVERED)

    downstream: list[BlastRadiusDownstreamV1] = []
    if command in _OUTAGE_COMMANDS:
        downstream = _downstream_chain(snapshot.edges, nodes_by_id, target_id=target_asset_id)

    warnings = _warnings(
        command=command,
        target=target,
        severed=severed,
        degraded=degraded,
        impacts=impacts,
        downstream=downstream,
    )

    return BlastRadiusPreviewV1(
        schema_version=BLAST_RADIUS_PREVIEW_SCHEMA_VERSION,
        run_id=run_id,
        command=command,
        target_asset_id=target_asset_id,
        action_class=action_class,
        severed_edge_count=severed,
        degraded_edge_count=degraded,
        impacted_assets=impacts,
        downstream_assets=downstream,
        warnings=warnings,
    )


def _direct_impacts(
    edges: list[GraphEdgeV1],
    nodes_by_id: dict[str, GraphNodeV1],
    *,
    command: ScenarioCommandTemplateV1,
    target_id: str,
) -> list[BlastRadiusImpactV1]:
    """1-hop neighbours affected by the action, one entry per affected edge."""
    impacts: list[BlastRadiusImpactV1] = []
    for edge in edges:
        if target_id not in (edge.source, edge.target):
            continue
        kind = _impact_kind(command, edge, target_id)
        if kind is None:
            continue
        neighbour_id = edge.target if edge.source == target_id else edge.source
        neighbour = nodes_by_id.get(neighbour_id)
        if neighbour is None:
            continue
        impacts.append(
            BlastRadiusImpactV1(
                asset_id=neighbour.id,
                label=neighbour.label,
                criticality=neighbour.criticality,
                status=_as_str(neighbour.status),
                relationship_type=_as_str(edge.relationship_type),
                impact_kind=kind,
                edge_id=edge.id,
            )
        )
    # Deterministic ordering: highest-criticality neighbour first, then asset id.
    impacts.sort(key=lambda i: (-i.criticality, i.asset_id))
    return impacts


def _impact_kind(
    command: ScenarioCommandTemplateV1,
    edge: GraphEdgeV1,
    target_id: str,
) -> BlastRadiusImpactKindV1 | None:
    """The impact kind an edge suffers under ``command``, or None if unaffected."""
    rel = edge.relationship_type
    if command is ScenarioCommandTemplateV1.ISOLATE:
        return BlastRadiusImpactKindV1.SEVERED
    if command in (
        ScenarioCommandTemplateV1.RESTRICT_ACCESS,
        ScenarioCommandTemplateV1.REVOKE_CREDENTIALS,
    ):
        return BlastRadiusImpactKindV1.DEGRADED if rel in _AUTH_RELATIONSHIPS else None
    if command is ScenarioCommandTemplateV1.RESTART_SERVICE:
        # Only assets that depend on the target see an outage: incoming dependency edges.
        if edge.target == target_id and rel in _DEPENDENCY_RELATIONSHIPS:
            return BlastRadiusImpactKindV1.OUTAGE
        return None
    if command is ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT:
        return BlastRadiusImpactKindV1.DEGRADED if rel in _DEPLOY_RELATIONSHIPS else None
    # OBSERVE / INCREASE_MONITORING: read-only.
    return None


def _downstream_chain(
    edges: list[GraphEdgeV1],
    nodes_by_id: dict[str, GraphNodeV1],
    *,
    target_id: str,
) -> list[BlastRadiusDownstreamV1]:
    """Transitive dependents reachable up the dependency chain from a downed target.

    Walks reverse dependency edges (``source`` DEPENDS_ON/HOSTED-BY ``target``): if the target
    goes down, everything that (transitively) needs it is affected. Bounded depth keeps the
    projection cheap and prevents cycles from looping.
    """
    # Reverse adjacency: for each asset, who depends on it.
    dependents: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relationship_type in _DEPENDENCY_RELATIONSHIPS:
            dependents.setdefault(edge.target, []).append(edge.source)

    hops_by_id: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(target_id, 0)])
    while queue:
        asset_id, depth = queue.popleft()
        if depth >= _MAX_CASCADE_DEPTH:
            continue
        for dependent_id in dependents.get(asset_id, []):
            if dependent_id == target_id or dependent_id in hops_by_id:
                continue
            hops_by_id[dependent_id] = depth + 1
            queue.append((dependent_id, depth + 1))

    chain: list[BlastRadiusDownstreamV1] = []
    for asset_id, hops in hops_by_id.items():
        node = nodes_by_id.get(asset_id)
        if node is None:
            continue
        chain.append(
            BlastRadiusDownstreamV1(
                asset_id=node.id,
                label=node.label,
                criticality=node.criticality,
                hops=hops,
            )
        )
    chain.sort(key=lambda d: (d.hops, -d.criticality, d.asset_id))
    return chain


def _warnings(
    *,
    command: ScenarioCommandTemplateV1,
    target: GraphNodeV1,
    severed: int,
    degraded: int,
    impacts: list[BlastRadiusImpactV1],
    downstream: list[BlastRadiusDownstreamV1],
) -> list[str]:
    """Human-readable, grounded warning strings (deterministic order)."""
    label = target.label
    warnings: list[str] = []

    if command is ScenarioCommandTemplateV1.ISOLATE:
        warnings.append(
            f"Isolation severs all {severed} connection(s) to {label}; "
            "dependent services lose their path to it."
        )
    elif command is ScenarioCommandTemplateV1.RESTRICT_ACCESS:
        warnings.append(
            f"Restricting access degrades {degraded} identity/auth edge(s); "
            f"legitimate callers to {label} may be denied."
        )
    elif command is ScenarioCommandTemplateV1.REVOKE_CREDENTIALS:
        warnings.append(
            f"Revoking credentials drops {degraded} authenticated/administered edge(s); "
            f"principals relying on {label} must re-enrol."
        )
    elif command is ScenarioCommandTemplateV1.RESTART_SERVICE:
        warnings.append(
            f"Restart briefly interrupts {degraded} dependent service(s) of {label}."
        )
    elif command is ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT:
        warnings.append(
            f"Rollback disturbs {degraded} deployment/hosting edge(s) around {label}."
        )
    else:
        warnings.append(f"{label} is monitored only; no edges are severed or degraded.")

    # High-criticality callout across both the direct and downstream sets.
    high_crit = sorted(
        _high_criticality_pairs(impacts, downstream),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if high_crit:
        top_label = high_crit[0][1]
        warnings.append(
            f"{len(high_crit)} high-criticality asset(s) affected, including {top_label}."
        )

    if len(downstream) > len(impacts) and command in _OUTAGE_COMMANDS:
        warnings.append(
            f"Impact cascades to {len(downstream)} service(s) down the dependency chain."
        )
    return warnings


def _high_criticality_pairs(
    impacts: list[BlastRadiusImpactV1],
    downstream: list[BlastRadiusDownstreamV1],
) -> list[tuple[float, str]]:
    """Distinct (criticality, label) for affected assets at or above the high threshold."""
    seen: dict[str, tuple[float, str]] = {}
    for item in impacts:
        if item.criticality >= _HIGH_CRITICALITY:
            seen[item.asset_id] = (item.criticality, item.label)
    for entry in downstream:
        if entry.criticality >= _HIGH_CRITICALITY:
            seen[entry.asset_id] = (entry.criticality, entry.label)
    return list(seen.values())
