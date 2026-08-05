"""Replay must reconstruct the run's real topology, not event-derived stubs.

The domain event stream carries only *changes* to the graph: an asset whose status never
moves emits nothing, and relationships are never emitted at all (``graph.snapshot.created``
is defined in the registry but no producer emits it). Reconstructing purely from events
therefore yields one stub node per asset an event happened to name — labelled with its own
id — and zero edges. These tests pin the baseline seed that closes that gap, using a
fixture whose field set is copied verbatim from a persisted ``graph_snapshots`` payload so
a shape drift in the writer fails here rather than silently emptying the operator's graph.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aegis_contracts import (
    GraphSnapshotV1,
    ObjectMetadataReferenceV1,
    ReplayModeV1,
    SnapshotManifestV1,
    parse_contract,
)
from aegis_persistence.object_storage import InMemoryObjectStorage
from aegis_replay.projectors import ReplayProjector, empty_provenance
from aegis_replay.service import ReplayService

from tests.replay.helpers import RUN_ID, sample_history

# Field-for-field the shape the snapshot writer persists (see
# ``PostgresGraphSnapshotRepository.add`` / ``build_graph_snapshot_from_runtime``): camelCase
# aliases, ``disclosed`` and ``appliedControls`` present, ``revision`` 0 at sequence 0.
BASELINE_PAYLOAD: dict[str, Any] = {
    "schemaVersion": 1,
    "runId": RUN_ID,
    "sequence": 0,
    "capturedAt": "2026-01-01T00:00:00Z",
    "nodes": [
        {
            "id": "asset:svc-api-gateway",
            "label": "API Gateway",
            "status": "normal",
            "revision": 0,
            "assetType": "service",
            "clusterId": "business-unit:platform",
            "disclosed": True,
            "riskScore": 0.05,
            "entityType": "asset",
            "criticality": 0.9,
            "schemaVersion": 1,
            "appliedControls": [],
        },
        {
            "id": "asset:device-workstation-01",
            "label": "Analyst Workstation 01",
            "status": "normal",
            "revision": 0,
            "assetType": "device",
            "clusterId": "business-unit:platform",
            "disclosed": True,
            "riskScore": 0.02,
            "entityType": "asset",
            "criticality": 0.4,
            "schemaVersion": 1,
            "appliedControls": [],
        },
        {
            "id": "asset:ai-model-logistics-router",
            "label": "Logistics Router Model",
            "status": "normal",
            "revision": 0,
            "assetType": "ai_model",
            "clusterId": "business-unit:ai-ops",
            "disclosed": True,
            "riskScore": 0.08,
            "entityType": "asset",
            "criticality": 0.82,
            "schemaVersion": 1,
            "appliedControls": [],
        },
        {
            "id": "asset:database-customer-pii",
            "label": "Customer PII Store",
            "status": "normal",
            "revision": 0,
            "assetType": "database",
            "clusterId": "business-unit:data",
            "disclosed": True,
            "riskScore": 0.11,
            "entityType": "asset",
            "criticality": 0.95,
            "schemaVersion": 1,
            "appliedControls": [],
        },
    ],
    "edges": [
        {
            "id": "edge:workstation-to-gateway",
            "source": "asset:device-workstation-01",
            "target": "asset:svc-api-gateway",
            "directed": True,
            "revision": 0,
            "confidence": 1.0,
            "eventCount": 1,
            "lastSeenAt": "2026-01-01T00:00:00Z",
            "firstSeenAt": "2026-01-01T00:00:00Z",
            "schemaVersion": 1,
            "relationshipType": "COMMUNICATED_WITH",
            "riskContribution": 0.1,
        },
        {
            "id": "edge:gateway-to-pii",
            "source": "asset:svc-api-gateway",
            "target": "asset:database-customer-pii",
            "directed": True,
            "revision": 0,
            "confidence": 1.0,
            "eventCount": 1,
            "lastSeenAt": "2026-01-01T00:00:00Z",
            "firstSeenAt": "2026-01-01T00:00:00Z",
            "schemaVersion": 1,
            "relationshipType": "DEPENDS_ON",
            "riskContribution": 0.15,
        },
        {
            "id": "edge:model-to-gateway",
            "source": "asset:ai-model-logistics-router",
            "target": "asset:svc-api-gateway",
            "directed": True,
            "revision": 0,
            "confidence": 1.0,
            "eventCount": 1,
            "lastSeenAt": "2026-01-01T00:00:00Z",
            "firstSeenAt": "2026-01-01T00:00:00Z",
            "schemaVersion": 1,
            "relationshipType": "AUTHENTICATED_TO",
            "riskContribution": 0.3,
        },
    ],
    "clusters": [],
    "revision": 0,
}


def baseline_snapshot(*, sequence: int = 0) -> GraphSnapshotV1:
    """Parse the fixture exactly as ``graph_snapshot_to_domain`` parses a persisted row."""
    payload = dict(BASELINE_PAYLOAD)
    payload["sequence"] = sequence
    return parse_contract(GraphSnapshotV1, payload)


class _FakeReplaySnapshotRepository:
    def __init__(self) -> None:
        self.manifests: dict[str, SnapshotManifestV1] = {}
        self.deleted: list[str] = []

    async def add(self, manifest: SnapshotManifestV1) -> SnapshotManifestV1:
        self.manifests[manifest.snapshot_id] = manifest
        return manifest

    async def get_by_id(self, snapshot_id: str) -> SnapshotManifestV1 | None:
        return self.manifests.get(snapshot_id)

    async def get_at_sequence(self, run_id: str, sequence: int) -> SnapshotManifestV1 | None:
        for manifest in self.manifests.values():
            if manifest.run_id == run_id and manifest.sequence == sequence:
                return manifest
        return None

    async def get_nearest_prior(
        self,
        run_id: str,
        sequence: int,
        *,
        compatible_only: bool = True,
    ) -> SnapshotManifestV1 | None:
        candidates = [
            manifest
            for manifest in self.manifests.values()
            if manifest.run_id == run_id
            and manifest.sequence <= sequence
            and (manifest.compatible or not compatible_only)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda manifest: manifest.sequence)

    async def list_for_run(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> list[SnapshotManifestV1]:
        return sorted(
            (manifest for manifest in self.manifests.values() if manifest.run_id == run_id),
            key=lambda manifest: manifest.sequence,
        )[:limit]

    async def mark_incompatible(self, snapshot_id: str) -> None:
        manifest = self.manifests.get(snapshot_id)
        if manifest is not None:
            self.manifests[snapshot_id] = manifest.model_copy(update={"compatible": False})

    async def delete(self, snapshot_id: str) -> None:
        self.deleted.append(snapshot_id)
        self.manifests.pop(snapshot_id, None)


class _FakeObjectRepository:
    def __init__(self) -> None:
        self.references: list[ObjectMetadataReferenceV1] = []

    async def add(self, reference: ObjectMetadataReferenceV1) -> ObjectMetadataReferenceV1:
        self.references.append(reference)
        return reference


class _FakeRunRepository:
    async def get_by_id(self, run_id: str) -> None:
        return None


class _FakeUnitOfWork:
    def __init__(self) -> None:
        self.replay_snapshots = _FakeReplaySnapshotRepository()
        self.objects = _FakeObjectRepository()
        self.runs = _FakeRunRepository()

    async def append_event(self, envelope: object) -> object:  # pragma: no cover - guarded
        return envelope


class _OfflineReplayService(ReplayService):
    """Replay service with both database reads stubbed, so the wiring can be tested offline.

    Only the two IO seams are replaced; sequence resolution, snapshot selection, projector
    seeding and event application all run for real.
    """

    def __init__(
        self,
        *,
        events_count: int = 20,
        baseline: GraphSnapshotV1 | None = None,
    ) -> None:
        super().__init__(InMemoryObjectStorage.create())
        self._events = sample_history(count=events_count)
        self._baseline = baseline

    async def _load_all_events(self, uow: object, run_id: str) -> list[Any]:  # type: ignore[override]
        return list(self._events)

    async def _load_topology_baseline(  # type: ignore[override]
        self,
        uow: object,
        run_id: str,
    ) -> GraphSnapshotV1 | None:
        return self._baseline


def test_persisted_graph_snapshot_shape_parses_into_the_replay_contract() -> None:
    """The writer's payload shape is what the replay read path parses — pin it."""
    snapshot = baseline_snapshot()
    assert len(snapshot.nodes) == 4
    assert len(snapshot.edges) == 3
    assert snapshot.sequence == 0
    assert snapshot.nodes[0].label == "API Gateway"


def test_projector_seeded_with_baseline_keeps_topology_through_event_application() -> None:
    projector = ReplayProjector(RUN_ID)
    projector.seed_topology(baseline_snapshot())
    for event in sample_history(count=20):
        projector.apply_event(event)

    state = projector.to_replay_state(
        provenance=empty_provenance(
            run_id=RUN_ID,
            mode=ReplayModeV1.FROM_EVENTS,
            applied_from=1,
            applied_to=20,
            applied_count=20,
        )
    )

    assert state.graph is not None
    assert {node.id for node in state.graph.nodes} == {
        "asset:svc-api-gateway",
        "asset:device-workstation-01",
        "asset:ai-model-logistics-router",
        "asset:database-customer-pii",
    }
    assert len(state.graph.edges) == 3

    by_id = {node.id: node for node in state.graph.nodes}
    # An asset the events touch keeps its real identity and gains the projected status.
    gateway = by_id["asset:svc-api-gateway"]
    assert gateway.label == "API Gateway"
    assert gateway.criticality == 0.9
    assert gateway.status.value == "under_investigation"
    assert gateway.risk_score == 0.77
    # An asset no event ever names survives untouched instead of vanishing.
    model = by_id["asset:ai-model-logistics-router"]
    assert model.label == "Logistics Router Model"
    assert model.status.value == "normal"


def test_reconstruct_from_events_returns_full_topology() -> None:
    service = _OfflineReplayService(baseline=baseline_snapshot())
    state = asyncio.run(
        service.reconstruct(
            _FakeUnitOfWork(),  # type: ignore[arg-type]
            run_id=RUN_ID,
            sequence=20,
            prefer_snapshot=False,
        )
    )
    assert state.graph is not None
    assert len(state.graph.nodes) == 4
    assert len(state.graph.edges) == 3
    assert state.provenance.mode is ReplayModeV1.FROM_EVENTS


def test_reconstruct_without_baseline_still_degrades_to_event_derived_stubs() -> None:
    """No baseline row is a data gap, not a crash: reconstruction must still answer."""
    service = _OfflineReplayService(baseline=None)
    state = asyncio.run(
        service.reconstruct(
            _FakeUnitOfWork(),  # type: ignore[arg-type]
            run_id=RUN_ID,
            sequence=20,
            prefer_snapshot=False,
        )
    )
    assert state.graph is not None
    assert state.graph.edges == []


def test_baseline_recorded_after_the_first_applied_event_is_rejected() -> None:
    """A later projection is not a baseline — replaying earlier events onto it rewinds it."""
    service = _OfflineReplayService(baseline=baseline_snapshot(sequence=5))
    state = asyncio.run(
        service.reconstruct(
            _FakeUnitOfWork(),  # type: ignore[arg-type]
            run_id=RUN_ID,
            sequence=20,
            prefer_snapshot=False,
        )
    )
    assert state.graph is not None
    assert "asset:ai-model-logistics-router" not in {node.id for node in state.graph.nodes}


def test_snapshot_accelerated_reconstruction_matches_event_only_reconstruction() -> None:
    """The baseline must not split the two reconstruction paths (AC1 equivalence)."""
    service = _OfflineReplayService(baseline=baseline_snapshot())
    uow = _FakeUnitOfWork()

    asyncio.run(service.create_snapshot(uow, run_id=RUN_ID, sequence=10))  # type: ignore[arg-type]

    live = asyncio.run(
        service.reconstruct(
            uow,  # type: ignore[arg-type]
            run_id=RUN_ID,
            sequence=20,
            prefer_snapshot=False,
        )
    )
    accelerated = asyncio.run(
        service.reconstruct(
            uow,  # type: ignore[arg-type]
            run_id=RUN_ID,
            sequence=20,
            prefer_snapshot=True,
        )
    )

    assert accelerated.provenance.mode is ReplayModeV1.FROM_SNAPSHOT_PLUS_EVENTS
    assert accelerated.provenance.snapshot_sequence == 10
    assert accelerated.graph is not None
    assert len(accelerated.graph.nodes) == 4
    assert len(accelerated.graph.edges) == 3
    assert accelerated.state_digest == live.state_digest


def test_empty_run_reconstruction_seeds_topology_deterministically() -> None:
    """A run with no events yet still has a topology, and its digest must be stable."""
    service = _OfflineReplayService(events_count=0, baseline=baseline_snapshot())
    service._events = []
    first = asyncio.run(
        service.reconstruct(_FakeUnitOfWork(), run_id=RUN_ID)  # type: ignore[arg-type]
    )
    second = asyncio.run(
        service.reconstruct(_FakeUnitOfWork(), run_id=RUN_ID)  # type: ignore[arg-type]
    )
    assert first.graph is not None
    assert len(first.graph.nodes) == 4
    assert first.state_digest == second.state_digest


def test_stale_snapshot_manifest_is_replaced_rather_than_blocking_resnapshot() -> None:
    """A manifest an older projector wrote must not make its sequence un-snapshottable."""
    from aegis_replay.snapshot_store import SnapshotStore

    service = _OfflineReplayService(baseline=baseline_snapshot())
    uow = _FakeUnitOfWork()

    stale = asyncio.run(service.create_snapshot(uow, run_id=RUN_ID, sequence=10))  # type: ignore[arg-type]
    # Model an archive written by a projector version this build no longer understands.
    store: SnapshotStore = service._store
    store._storage.delete(object_key=stale.object_key)  # type: ignore[attr-defined]

    replacement = asyncio.run(
        service.create_snapshot(uow, run_id=RUN_ID, sequence=10)  # type: ignore[arg-type]
    )

    assert replacement.snapshot_id != stale.snapshot_id
    assert uow.replay_snapshots.deleted == [stale.snapshot_id]
