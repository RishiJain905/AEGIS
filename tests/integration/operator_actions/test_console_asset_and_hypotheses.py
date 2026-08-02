"""Phase 7 console asset deep-dive + operator-pinned hypothesis integration tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from aegis_agents.runtime.ids import new_runtime_id
from aegis_api.console.service import ConsoleService
from aegis_api.operator_actions.events import build_operator_action_proposed_event
from aegis_api.operator_actions.service import OperatorActionService
from aegis_contracts import (
    GraphEdgeV1,
    GraphNodeV1,
    GraphSnapshotV1,
    OperatorHypothesisRequestV1,
    load_settings,
)
from aegis_contracts.graph import AssetType, NodeStatus, RelationshipType
from aegis_contracts.versioning import (
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    OPERATOR_HYPOTHESIS_REQUEST_SCHEMA_VERSION,
)
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)

_ASSET = "asset:svc-api-gateway"
_PEER = "asset:db-primary"


def _session_maker():
    return get_session_maker(load_settings(), engine=create_engine(load_settings()))


async def _seed_graph(uow, run_id: str) -> None:
    now = datetime(2026, 6, 30, 2, 0, 0, tzinfo=UTC)
    snapshot = GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=run_id,
        sequence=100,
        captured_at=now,
        nodes=[
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id=_ASSET,
                entity_type="asset",
                asset_type=AssetType.SERVICE,
                label="API Gateway",
                cluster_id="business-unit:bu-platform",
                risk_score=0.78,
                criticality=0.91,
                status=NodeStatus.UNDER_INVESTIGATION,
                revision=1,
            ),
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id=_PEER,
                entity_type="asset",
                asset_type=AssetType.DATABASE,
                label="Primary DB",
                cluster_id="business-unit:bu-platform",
                risk_score=0.4,
                criticality=0.8,
                status=NodeStatus.NORMAL,
                revision=1,
            ),
        ],
        edges=[
            GraphEdgeV1(
                schema_version=GRAPH_EDGE_SCHEMA_VERSION,
                id="edge:gw-db",
                source=_ASSET,
                target=_PEER,
                relationship_type=RelationshipType.COMMUNICATED_WITH,
                directed=True,
                confidence=1.0,
                risk_contribution=0.2,
                first_seen_at=now,
                last_seen_at=now,
                event_count=1,
                revision=1,
            ),
        ],
        clusters=[],
        revision=1,
    )
    await PostgresGraphSnapshotRepository(uow.session).add(snapshot)
    seq = await uow.events.next_sequence(run_id)
    await uow.append_event(
        build_operator_action_proposed_event(
            event_id=new_runtime_id("evt"),
            run_id=run_id,
            sequence=seq,
            actor_id="user:op",
            trace_id=new_runtime_id("trc"),
            proposal_id=new_runtime_id("prp"),
            incident_id="incident:inc_op_asset",
            scenario_command="isolate",
            action_class="class_2",
            target_asset_id=_ASSET,
            justification="Seeded operator order for the asset-detail projection.",
        )
    )


@pytest.mark.asyncio
async def test_asset_detail_returns_node_relationships_and_events() -> None:
    service = ConsoleService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        await _seed_graph(uow, run_id)
        detail = await service.asset_detail(uow, run_id=run_id, asset_id=_ASSET)

    assert detail is not None
    assert detail.asset_id == _ASSET
    assert detail.label == "API Gateway"
    assert detail.status == "under_investigation"
    assert detail.cluster_id == "business-unit:bu-platform"
    assert len(detail.relationships) == 1
    rel = detail.relationships[0]
    assert rel.target_asset_id == _PEER
    assert rel.direction == "outbound"
    assert any(e.asset_id == _ASSET for e in detail.recent_events)


@pytest.mark.asyncio
async def test_asset_detail_missing_asset_returns_none() -> None:
    service = ConsoleService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        await _seed_graph(uow, run_id)
        missing = await service.asset_detail(uow, run_id=run_id, asset_id="asset:nope")
    assert missing is None


@pytest.mark.asyncio
async def test_operator_pinned_hypothesis_round_trips() -> None:
    service = OperatorActionService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        created = await service.create_hypothesis(
            uow,
            run_id=run_id,
            request=OperatorHypothesisRequestV1(
                schema_version=OPERATOR_HYPOTHESIS_REQUEST_SCHEMA_VERSION,
                statement="The API gateway is the initial access point",
                asset_ids=[_ASSET],
                confidence=0.7,
            ),
            actor_id="user:op",
        )
        listed = await service.list_hypotheses(uow, run_id=run_id)

    assert created.statement == "The API gateway is the initial access point"
    assert created.confidence == 0.7
    assert any(h.id == created.id for h in listed)


@pytest.mark.asyncio
async def test_list_operator_hypotheses_empty_without_anchor() -> None:
    service = OperatorActionService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        # No operator incident anchor created yet -> empty, and no incident is created on read.
        listed = await service.list_hypotheses(uow, run_id=run_id)
    assert listed == []
