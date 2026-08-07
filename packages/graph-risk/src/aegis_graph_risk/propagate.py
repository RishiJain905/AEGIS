"""Deterministic bounded graph risk propagation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from aegis_contracts.graph import GraphSnapshotV1
from aegis_contracts.risk import (
    AssetRiskScoreV1,
    RiskContributionV1,
    RiskEngineConfigV1,
    RiskExplanationPathV1,
    RiskInputV1,
    RiskPathHopV1,
    RiskProjectionDeltaV1,
    RiskProjectionNodeUpdateV1,
    RiskSignalStatus,
)
from aegis_contracts.versioning import (
    ASSET_RISK_SCORE_SCHEMA_VERSION,
    RISK_CONTRIBUTION_SCHEMA_VERSION,
    RISK_EXPLANATION_PATH_SCHEMA_VERSION,
    RISK_PROJECTION_DELTA_SCHEMA_VERSION,
)

from aegis_graph_risk.errors import GraphRiskError, GraphRiskErrorCode
from aegis_graph_risk.graph_index import GraphIndex, build_graph_index, validate_snapshot_entities
from aegis_graph_risk.posture import posture_risk
from aegis_graph_risk.version import GRAPH_RISK_ALGORITHM_VERSION


@dataclass(slots=True)
class RiskPropagationResult:
    scores: list[AssetRiskScoreV1]
    projection_delta: RiskProjectionDeltaV1
    checksum: str


@dataclass(slots=True)
class _PathState:
    node_ids: list[str]
    hops: list[RiskPathHopV1]
    edge_weight_product: float


def _temporal_decay(
    signal: RiskInputV1,
    *,
    current_sim_time: datetime,
    config: RiskEngineConfigV1,
) -> float:
    if signal.status != RiskSignalStatus.ACTIVE:
        return 0.0
    age_seconds = max(0.0, (current_sim_time - signal.sim_time).total_seconds())
    exponent = age_seconds / config.temporal_half_life_seconds
    return float(config.temporal_decay_factor**exponent)


def _criticality_factor(node_criticality: float, config: RiskEngineConfigV1) -> float:
    return 1.0 + node_criticality * config.criticality_amplifier


def _signal_strength(signal: RiskInputV1) -> float:
    return signal.strength * signal.confidence


def _build_explanation_path(
    signal: RiskInputV1,
    target_asset_id: str,
    state: _PathState,
    *,
    hop_count: int,
    distance_decay: float,
    temporal_decay: float,
    criticality_factor: float,
    contribution: float,
) -> RiskExplanationPathV1:
    if len(state.node_ids) < 2 or len(state.hops) != len(state.node_ids) - 1:
        raise GraphRiskError(
            code=GraphRiskErrorCode.MALFORMED_PATH,
            message="Explanation path nodes and hops are inconsistent",
            details={"nodeCount": len(state.node_ids), "hopCount": len(state.hops)},
        )
    return RiskExplanationPathV1(
        schema_version=RISK_EXPLANATION_PATH_SCHEMA_VERSION,
        signal_id=signal.signal_id,
        origin_asset_id=signal.asset_id,
        target_asset_id=target_asset_id,
        node_ids=state.node_ids,
        hops=state.hops,
        hop_count=hop_count,
        distance_decay=distance_decay,
        temporal_decay=temporal_decay,
        criticality_factor=criticality_factor,
        contribution=contribution,
        algorithm_version=GRAPH_RISK_ALGORITHM_VERSION,
    )


def _contribution_from_path(
    signal: RiskInputV1,
    target_asset_id: str,
    state: _PathState,
    *,
    hop_count: int,
    distance_decay: float,
    temporal_decay: float,
    criticality_factor: float,
) -> RiskContributionV1:
    contribution = min(
        1.0,
        _signal_strength(signal)
        * state.edge_weight_product
        * distance_decay
        * temporal_decay
        * criticality_factor,
    )
    explanation = _build_explanation_path(
        signal,
        target_asset_id,
        state,
        hop_count=hop_count,
        distance_decay=distance_decay,
        temporal_decay=temporal_decay,
        criticality_factor=criticality_factor,
        contribution=contribution,
    )
    return RiskContributionV1(
        schema_version=RISK_CONTRIBUTION_SCHEMA_VERSION,
        signal_id=signal.signal_id,
        origin_asset_id=signal.asset_id,
        target_asset_id=target_asset_id,
        amount=contribution,
        hop_count=hop_count,
        distance_decay=distance_decay,
        temporal_decay=temporal_decay,
        criticality_factor=criticality_factor,
        explanation_path=explanation,
    )


def _propagate_signal(
    signal: RiskInputV1,
    index: GraphIndex,
    config: RiskEngineConfigV1,
    *,
    current_sim_time: datetime,
    allowed_nodes: set[str] | None,
) -> dict[str, list[RiskContributionV1]]:
    if signal.asset_id not in index.nodes:
        raise GraphRiskError(
            code=GraphRiskErrorCode.MISSING_ENTITY,
            message=f"Risk origin asset not found: {signal.asset_id}",
            details={"assetId": signal.asset_id},
        )

    temporal_decay = _temporal_decay(signal, current_sim_time=current_sim_time, config=config)
    if temporal_decay <= 0.0:
        return {}

    contributions_by_node: dict[str, list[RiskContributionV1]] = {}
    queue: list[tuple[_PathState, int]] = [
        (_PathState(node_ids=[signal.asset_id], hops=[], edge_weight_product=1.0), 0)
    ]

    while queue:
        state, hop_count = queue.pop(0)
        current_node = state.node_ids[-1]
        if allowed_nodes is not None and current_node not in allowed_nodes:
            continue

        if hop_count > 0:
            distance_decay = config.distance_decay_factor**hop_count
            node = index.nodes[current_node]
            crit_factor = _criticality_factor(node.criticality, config)
            contribution = _contribution_from_path(
                signal,
                current_node,
                state,
                hop_count=hop_count,
                distance_decay=distance_decay,
                temporal_decay=temporal_decay,
                criticality_factor=crit_factor,
            )
            if contribution.amount >= config.min_explanation_contribution:
                contributions_by_node.setdefault(current_node, []).append(contribution)

        if hop_count >= config.max_hops:
            continue

        for neighbor_id, indexed in index.neighbors(current_node):
            if neighbor_id in state.node_ids:
                continue
            if allowed_nodes is not None and neighbor_id not in allowed_nodes:
                continue
            hop = RiskPathHopV1(
                edge_id=indexed.edge.id,
                source_id=indexed.edge.source,
                target_id=indexed.edge.target,
                relationship_type=indexed.edge.relationship_type,
                edge_weight=indexed.weight,
                hop_index=hop_count + 1,
            )
            next_state = _PathState(
                node_ids=[*state.node_ids, neighbor_id],
                hops=[*state.hops, hop],
                edge_weight_product=state.edge_weight_product * indexed.weight,
            )
            queue.append((next_state, hop_count + 1))

    return contributions_by_node


def _incident_subgraph_nodes(
    index: GraphIndex,
    seed_asset_ids: list[str],
    *,
    max_hops: int,
) -> set[str]:
    allowed: set[str] = set()
    for seed in sorted(seed_asset_ids):
        if seed not in index.nodes:
            raise GraphRiskError(
                code=GraphRiskErrorCode.MISSING_ENTITY,
                message=f"Incident seed asset not found: {seed}",
                details={"assetId": seed},
            )
        frontier = {seed}
        visited = {seed}
        for _hop in range(max_hops):
            next_frontier: set[str] = set()
            for node_id in sorted(frontier):
                for neighbor_id, _indexed in index.neighbors(node_id):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.add(neighbor_id)
            frontier = next_frontier
        allowed.update(visited)
    return allowed


def compute_risk_scores(
    snapshot: GraphSnapshotV1,
    signals: list[RiskInputV1],
    config: RiskEngineConfigV1,
    *,
    current_sim_time: datetime,
    computed_at_sequence: int,
    incident_seed_asset_ids: list[str] | None = None,
) -> RiskPropagationResult:
    if config.algorithm_version != GRAPH_RISK_ALGORITHM_VERSION:
        raise GraphRiskError(
            code=GraphRiskErrorCode.INCOMPATIBLE_ALGORITHM,
            message=f"Unsupported algorithm version: {config.algorithm_version}",
            details={"algorithmVersion": config.algorithm_version},
        )

    validate_snapshot_entities(snapshot, {signal.asset_id for signal in signals})
    eligible = set(config.eligible_relationship_types)
    index = build_graph_index(
        snapshot,
        eligible_types=eligible,
        relationship_type_weights=config.relationship_type_weights,
    )
    allowed_nodes = None
    if incident_seed_asset_ids:
        allowed_nodes = _incident_subgraph_nodes(
            index,
            incident_seed_asset_ids,
            max_hops=config.max_hops,
        )

    direct_by_node: dict[str, float] = {}
    propagated_contributions: dict[str, list[RiskContributionV1]] = {}

    for signal in sorted(signals, key=lambda item: item.signal_id):
        strength = _signal_strength(signal)
        if signal.status == RiskSignalStatus.ACTIVE and strength > 0.0:
            current_direct = direct_by_node.get(signal.asset_id, 0.0)
            direct_by_node[signal.asset_id] = max(current_direct, strength)

        signal_contribs = _propagate_signal(
            signal,
            index,
            config,
            current_sim_time=current_sim_time,
            allowed_nodes=allowed_nodes,
        )
        for node_id, contribs in signal_contribs.items():
            propagated_contributions.setdefault(node_id, []).extend(contribs)

    scores: list[AssetRiskScoreV1] = []
    node_updates: list[RiskProjectionNodeUpdateV1] = []

    for node in sorted(snapshot.nodes, key=lambda item: item.id):
        if allowed_nodes is not None and node.id not in allowed_nodes:
            continue
        # An asset's own posture is direct risk: the attacker owns this host whether or not
        # a detector happened to fire on it. Folding the posture floor into ``direct``
        # (rather than bolting a third component onto the score) keeps the inspector's
        # Direct/Propagated breakdown honest — direct is "risk originating here", and being
        # compromised originates here — and it means the engine can never report an asset
        # as safer than the graph already shows it to be.
        posture_floor = posture_risk(
            node.status.value,
            node.criticality,
            authored_floor=node.risk_score,
        )
        direct = max(direct_by_node.get(node.id, 0.0), posture_floor)
        node_contribs = propagated_contributions.get(node.id, [])
        propagated = 0.0
        if node_contribs:
            propagated = max(contrib.amount for contrib in node_contribs)
        total = min(config.global_cap, direct + propagated)
        top_contribs = sorted(
            node_contribs,
            key=lambda item: (-item.amount, item.signal_id, item.origin_asset_id),
        )[: config.top_explanation_paths]

        if total <= 0.0 and direct <= 0.0 and propagated <= 0.0:
            continue

        scores.append(
            AssetRiskScoreV1(
                schema_version=ASSET_RISK_SCORE_SCHEMA_VERSION,
                run_id=snapshot.run_id,
                asset_id=node.id,
                total=total,
                direct=direct,
                propagated=propagated,
                algorithm_version=GRAPH_RISK_ALGORITHM_VERSION,
                computed_at_sequence=computed_at_sequence,
                sim_time=current_sim_time,
                top_contributions=top_contribs,
            )
        )
        node_updates.append(
            RiskProjectionNodeUpdateV1(
                asset_id=node.id,
                risk_score=total,
                direct=direct,
                propagated=propagated,
                revision=node.revision + 1,
            )
        )

    projection_delta = RiskProjectionDeltaV1(
        schema_version=RISK_PROJECTION_DELTA_SCHEMA_VERSION,
        run_id=snapshot.run_id,
        sequence=computed_at_sequence,
        algorithm_version=GRAPH_RISK_ALGORITHM_VERSION,
        node_updates=node_updates or [
            RiskProjectionNodeUpdateV1(
                asset_id=snapshot.nodes[0].id,
                risk_score=0.0,
                direct=0.0,
                propagated=0.0,
                revision=snapshot.nodes[0].revision,
            )
        ],
    )

    checksum = hashlib.sha256(
        json.dumps(
            [score.model_dump(mode="json", by_alias=True) for score in scores],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    return RiskPropagationResult(
        scores=scores,
        projection_delta=projection_delta,
        checksum=f"sha256:{checksum}",
    )
