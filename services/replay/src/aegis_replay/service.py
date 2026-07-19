"""Phase 25 replay reconstruction service (read-only over live state)."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import (
    DomainEventEnvelopeV1,
    ReplayCursorV1,
    ReplayEquivalenceResultV1,
    ReplayModeV1,
    ReplayStateV1,
    SnapshotManifestV1,
    SnapshotTriggerReasonV1,
    StateDiffV1,
)
from aegis_contracts.replay import ReplayErrorCode
from aegis_contracts.versioning import (
    REPLAY_CURSOR_SCHEMA_VERSION,
    REPLAY_EQUIVALENCE_RESULT_SCHEMA_VERSION,
)
from aegis_persistence.object_storage import ObjectStoragePort
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION

from aegis_replay.diff import diff_states
from aegis_replay.errors import ReplayEngineError
from aegis_replay.projectors import ReplayProjector, empty_provenance
from aegis_replay.snapshot_store import SnapshotStore
from aegis_replay.versioning import DEFAULT_SNAPSHOT_INTERVAL


class ReplayService:
    """Reconstruct historical application state without mutating live runs."""

    def __init__(
        self,
        storage: ObjectStoragePort,
        *,
        snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
        engine_version: str = SIMULATION_ENGINE_VERSION,
        page_size: int = 1000,
    ) -> None:
        self._store = SnapshotStore(storage)
        self._snapshot_interval = max(1, snapshot_interval)
        self._engine_version = engine_version
        self._page_size = page_size

    def assert_read_only(self, uow: PostgresUnitOfWork) -> None:
        """Mechanically prevent replay from appending authoritative events/outbox rows.

        Replaces the unit of work's ``append_event`` — the single choke point through which
        every domain event and its outbox row is written — with a guard that fails closed.
        This turns replay isolation from a convention into an enforced boundary: any code
        path (present or future) that tries to append live state during replay raises
        ``REPLAY_LIVE_MUTATION_FORBIDDEN`` instead of silently mutating authoritative tables.

        Acceleration-snapshot writes (``replay_snapshots`` + object storage) do not flow
        through ``append_event`` and remain permitted, matching the architecture rule that
        snapshots accelerate reconstruction while ``domain_events`` stay authoritative.
        Idempotent: re-arming an already-guarded unit of work is a no-op.
        """
        if getattr(uow, "_aegis_replay_read_only", False):
            return

        async def _blocked_append(*_args: object, **_kwargs: object) -> object:
            raise ReplayEngineError(
                ReplayErrorCode.REPLAY_LIVE_MUTATION_FORBIDDEN,
                "Replay context is read-only; appending live events is forbidden",
            )

        uow.append_event = _blocked_append  # type: ignore[method-assign]
        uow._aegis_replay_read_only = True  # type: ignore[attr-defined]

    async def reconstruct(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        sequence: int | None = None,
        sim_time: datetime | None = None,
        incident_id: str | None = None,
        prefer_snapshot: bool = True,
    ) -> ReplayStateV1:
        import time

        started = time.perf_counter()
        status = "ok"
        try:
            result = await self._reconstruct_impl(
                uow,
                run_id=run_id,
                sequence=sequence,
                sim_time=sim_time,
                incident_id=incident_id,
                prefer_snapshot=prefer_snapshot,
            )
            try:
                from aegis_observability.instrumentation import record_replay

                event_count = int(getattr(result.provenance, "applied_count", 0) or 0)
                record_replay(
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    status=status,
                    event_count=event_count,
                )
            except Exception:  # noqa: BLE001
                pass
            return result
        except Exception:
            status = "error"
            try:
                from aegis_observability.instrumentation import record_replay

                record_replay(
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    status=status,
                )
            except Exception:  # noqa: BLE001
                pass
            raise

    async def _reconstruct_impl(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        sequence: int | None = None,
        sim_time: datetime | None = None,
        incident_id: str | None = None,
        prefer_snapshot: bool = True,
    ) -> ReplayStateV1:
        self.assert_read_only(uow)
        events = await self._load_all_events(uow, run_id)
        if not events and sequence is None and sim_time is None:
            provenance = empty_provenance(
                run_id=run_id,
                mode=ReplayModeV1.FROM_EVENTS,
                applied_from=0,
                applied_to=0,
                applied_count=0,
            )
            projector = ReplayProjector(run_id)
            return projector.to_replay_state(provenance=provenance, incident_id=incident_id)

        target_sequence = self._resolve_target_sequence(
            events,
            sequence=sequence,
            sim_time=sim_time,
        )
        self._assert_sequence_contiguous(events, up_to=target_sequence)

        fallback_reason: str | None = None
        snapshot_state: ReplayStateV1 | None = None
        snapshot_id: str | None = None
        snapshot_sequence: int | None = None
        mode = ReplayModeV1.FROM_EVENTS
        apply_from = 0

        if prefer_snapshot:
            manifest = await uow.replay_snapshots.get_nearest_prior(run_id, target_sequence)
            if manifest is not None:
                try:
                    snapshot = await self._store.load_snapshot(
                        uow,
                        manifest.snapshot_id,
                        expected_engine_version=None,
                    )
                    snapshot_state = snapshot.state
                    snapshot_id = snapshot.id
                    snapshot_sequence = snapshot.sequence
                    apply_from = snapshot.sequence + 1
                    mode = ReplayModeV1.FROM_SNAPSHOT_PLUS_EVENTS
                except ReplayEngineError as exc:
                    if exc.code in {
                        ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH,
                        ReplayErrorCode.SNAPSHOT_INCOMPATIBLE,
                        ReplayErrorCode.SNAPSHOT_MISSING,
                    }:
                        fallback_reason = f"{exc.code.value}: {exc.message}"
                        # Try earlier snapshots until none remain.
                        earlier = await uow.replay_snapshots.list_for_run(run_id)
                        for candidate in reversed(
                            [m for m in earlier if m.sequence < manifest.sequence]
                        ):
                            try:
                                snapshot = await self._store.load_snapshot(
                                    uow,
                                    candidate.snapshot_id,
                                )
                                snapshot_state = snapshot.state
                                snapshot_id = snapshot.id
                                snapshot_sequence = snapshot.sequence
                                apply_from = snapshot.sequence + 1
                                mode = ReplayModeV1.FROM_SNAPSHOT_PLUS_EVENTS
                                fallback_reason = (
                                    f"{fallback_reason}; recovered via snapshot "
                                    f"{candidate.snapshot_id}"
                                )
                                break
                            except ReplayEngineError:
                                continue
                        if snapshot_state is None:
                            mode = ReplayModeV1.FROM_EVENTS
                            apply_from = 0
                    else:
                        raise

        if snapshot_state is not None:
            projector = ReplayProjector.from_replay_state(snapshot_state)
        else:
            projector = ReplayProjector(run_id)

        applied: list[DomainEventEnvelopeV1] = [
            event
            for event in events
            if apply_from <= event.sequence <= target_sequence
        ]
        for event in applied:
            projector.apply_event(event)

        applied_from = apply_from if applied else (snapshot_sequence or 0)
        applied_to = applied[-1].sequence if applied else (snapshot_sequence or 0)
        provenance = empty_provenance(
            run_id=run_id,
            mode=mode,
            applied_from=applied_from,
            applied_to=applied_to,
            applied_count=len(applied),
            snapshot_id=snapshot_id,
            snapshot_sequence=snapshot_sequence,
            fallback_reason=fallback_reason,
        )
        return projector.to_replay_state(provenance=provenance, incident_id=incident_id)

    async def create_snapshot(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        sequence: int | None = None,
        trigger_reason: SnapshotTriggerReasonV1 = SnapshotTriggerReasonV1.EXPLICIT_REQUEST,
    ) -> SnapshotManifestV1:
        self.assert_read_only(uow)
        state = await self.reconstruct(
            uow,
            run_id=run_id,
            sequence=sequence,
            prefer_snapshot=True,
        )
        run = await uow.runs.get_by_id(run_id)
        scenario_version_id = (
            run.scenario_version_id if run is not None else "scenario-version:unknown"
        )
        manifest, _snapshot = await self._store.create_snapshot(
            uow,
            state=state,
            scenario_version_id=scenario_version_id,
            engine_version=self._engine_version,
            trigger_reason=trigger_reason,
            event_range_from=0,
        )
        return manifest

    async def maybe_create_cadence_snapshot(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        latest_sequence: int,
        trigger_reason: SnapshotTriggerReasonV1 = SnapshotTriggerReasonV1.SEQUENCE_INTERVAL,
    ) -> SnapshotManifestV1 | None:
        if latest_sequence <= 0:
            return None
        if latest_sequence % self._snapshot_interval != 0:
            return None
        existing = await uow.replay_snapshots.get_at_sequence(run_id, latest_sequence)
        if existing is not None:
            return existing
        return await self.create_snapshot(
            uow,
            run_id=run_id,
            sequence=latest_sequence,
            trigger_reason=trigger_reason,
        )

    async def list_snapshots(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
    ) -> list[SnapshotManifestV1]:
        return await uow.replay_snapshots.list_for_run(run_id)

    async def diff(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        from_sequence: int,
        to_sequence: int,
    ) -> StateDiffV1:
        from_state = await self.reconstruct(uow, run_id=run_id, sequence=from_sequence)
        to_state = await self.reconstruct(uow, run_id=run_id, sequence=to_sequence)
        return diff_states(from_state, to_state)

    async def check_equivalence(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        sequence: int | None = None,
    ) -> ReplayEquivalenceResultV1:
        """Compare full-event reconstruction vs snapshot-accelerated reconstruction."""
        events = await self._load_all_events(uow, run_id)
        target = sequence if sequence is not None else (events[-1].sequence if events else 0)
        live = await self.reconstruct(
            uow,
            run_id=run_id,
            sequence=target,
            prefer_snapshot=False,
        )
        reconstructed = await self.reconstruct(
            uow,
            run_id=run_id,
            sequence=target,
            prefer_snapshot=True,
        )
        diff = diff_states(live, reconstructed)
        equivalent = live.state_digest == reconstructed.state_digest or diff.equivalent
        return ReplayEquivalenceResultV1(
            schema_version=REPLAY_EQUIVALENCE_RESULT_SCHEMA_VERSION,
            run_id=run_id,  # type: ignore[arg-type]
            sequence=target,
            live_digest=live.state_digest,
            reconstructed_digest=reconstructed.state_digest,
            equivalent=equivalent,
            diff=None if equivalent else diff,
            provenance=reconstructed.provenance,
            checked_at=datetime.now(tz=UTC),
        )

    async def cursor_at(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        sequence: int | None = None,
        sim_time: datetime | None = None,
        incident_id: str | None = None,
    ) -> ReplayCursorV1:
        state = await self.reconstruct(
            uow,
            run_id=run_id,
            sequence=sequence,
            sim_time=sim_time,
            incident_id=incident_id,
        )
        return state.cursor

    def build_cursor(
        self,
        *,
        run_id: str,
        sequence: int,
        sim_time: datetime | None = None,
        incident_id: str | None = None,
    ) -> ReplayCursorV1:
        return ReplayCursorV1(
            schema_version=REPLAY_CURSOR_SCHEMA_VERSION,
            run_id=run_id,  # type: ignore[arg-type]
            sequence=sequence,
            sim_time=sim_time,
            incident_id=incident_id,  # type: ignore[arg-type]
        )

    async def _load_all_events(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
    ) -> list[DomainEventEnvelopeV1]:
        query = PostgresEventQueryRepository(uow.session)
        events: list[DomainEventEnvelopeV1] = []
        from_sequence = 0
        while True:
            page = await query.list_by_run(
                run_id,
                from_sequence=from_sequence,
                limit=self._page_size,
            )
            if not page:
                break
            events.extend(page)
            next_from = page[-1].sequence + 1
            if next_from <= from_sequence:
                break
            from_sequence = next_from
            if len(page) < self._page_size:
                break
        # Deduplicate by eventId while preserving sequence order.
        seen: set[str] = set()
        deduped: list[DomainEventEnvelopeV1] = []
        for event in sorted(events, key=lambda item: item.sequence):
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            deduped.append(event)
        return deduped

    def _resolve_target_sequence(
        self,
        events: list[DomainEventEnvelopeV1],
        *,
        sequence: int | None,
        sim_time: datetime | None,
    ) -> int:
        if not events:
            if sequence is not None:
                return sequence
            return 0
        if sequence is not None:
            max_seq = events[-1].sequence
            if sequence > max_seq:
                raise ReplayEngineError(
                    ReplayErrorCode.REPLAY_VALIDATION_FAILED,
                    "Requested sequence exceeds available event history",
                    details={"sequence": sequence, "maxSequence": max_seq},
                )
            return sequence
        if sim_time is not None:
            matched = [event for event in events if event.sim_time <= sim_time]
            if not matched:
                return 0
            return matched[-1].sequence
        return events[-1].sequence

    def _assert_sequence_contiguous(
        self,
        events: list[DomainEventEnvelopeV1],
        *,
        up_to: int,
    ) -> None:
        relevant = [event for event in events if event.sequence <= up_to]
        if not relevant:
            return
        # Detect gaps in the authoritative sequence stream.
        expected = relevant[0].sequence
        for event in relevant:
            if event.sequence != expected:
                raise ReplayEngineError(
                    ReplayErrorCode.REPLAY_SEQUENCE_GAP,
                    "Event sequence gap or mismatch detected",
                    details={
                        "expectedSequence": expected,
                        "actualSequence": event.sequence,
                        "eventId": event.event_id,
                    },
                )
            expected += 1
