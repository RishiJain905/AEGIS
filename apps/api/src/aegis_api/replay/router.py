"""Read-only snapshot and replay HTTP routes (Phase 25).

These endpoints reconstruct historical state. They never append domain events,
approve proposals, or mutate live run tables beyond snapshot artifact writes.
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from aegis_contracts import (
    PermissionV1,
    ReplayCursorV1,
    ReplayEquivalenceResultV1,
    ReplayStateV1,
    SnapshotManifestV1,
    SnapshotTriggerReasonV1,
    StateDiffV1,
    load_settings,
)
from aegis_persistence.object_storage import build_object_storage
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_replay.errors import ReplayEngineError
from aegis_replay.service import ReplayService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from aegis_api.auth.deps import require_permission
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1/replay", tags=["replay"])

SimTimeQuery = Annotated[datetime | None, Query(alias="simTime")]
IncidentIdQuery = Annotated[str | None, Query(alias="incidentId")]
PreferSnapshotQuery = Annotated[bool, Query(alias="preferSnapshot")]
SequenceQuery = Annotated[int | None, Query(ge=0)]
FromSequenceQuery = Annotated[int, Query(alias="fromSequence", ge=0)]
ToSequenceQuery = Annotated[int, Query(alias="toSequence", ge=0)]
IncludeEquivalenceQuery = Annotated[bool, Query(alias="includeEquivalence")]


class CreateSnapshotRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sequence: int | None = Field(default=None, ge=0)
    trigger_reason: SnapshotTriggerReasonV1 = Field(
        default=SnapshotTriggerReasonV1.EXPLICIT_REQUEST,
        alias="triggerReason",
    )


class DiagnosticHarnessResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: str = "historical_replay"
    live_mutation_allowed: bool = Field(default=False, alias="liveMutationAllowed")
    run_id: str = Field(alias="runId")
    state: ReplayStateV1
    snapshots: list[SnapshotManifestV1]
    equivalence: ReplayEquivalenceResultV1 | None = None


@lru_cache(maxsize=1)
def _replay_service() -> ReplayService:
    settings = load_settings()
    filesystem_root = os.environ.get("AEGIS_REPLAY_STORAGE_DIR")
    in_memory = os.environ.get("AEGIS_REPLAY_IN_MEMORY_STORAGE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    storage = build_object_storage(
        settings,
        in_memory=in_memory and not filesystem_root,
        filesystem_root=filesystem_root,
    )
    return ReplayService(storage)


def _http_error(exc: ReplayEngineError) -> HTTPException:
    status = 400
    if exc.code.value in {"SNAPSHOT_MISSING", "REPLAY_NOT_FOUND"}:
        status = 404
    elif exc.code.value == "REPLAY_LIVE_MUTATION_FORBIDDEN":
        status = 403
    return HTTPException(
        status_code=status,
        detail={
            "code": exc.code.value,
            "message": exc.message,
            "details": exc.details,
            "mode": "historical_replay",
        },
    )


@router.get("/runs/{run_id}/state", response_model=ReplayStateV1)
async def get_replay_state(
    run_id: str,
    sequence: SequenceQuery = None,
    sim_time: SimTimeQuery = None,
    incident_id: IncidentIdQuery = None,
    prefer_snapshot: PreferSnapshotQuery = True,
) -> ReplayStateV1:
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await service.reconstruct(
                uow,
                run_id=run_id,
                sequence=sequence,
                sim_time=sim_time,
                incident_id=incident_id,
                prefer_snapshot=prefer_snapshot,
            )
        except ReplayEngineError as exc:
            raise _http_error(exc) from exc


@router.get("/runs/{run_id}/cursor", response_model=ReplayCursorV1)
async def get_replay_cursor(
    run_id: str,
    sequence: SequenceQuery = None,
    sim_time: SimTimeQuery = None,
    incident_id: IncidentIdQuery = None,
) -> ReplayCursorV1:
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await service.cursor_at(
                uow,
                run_id=run_id,
                sequence=sequence,
                sim_time=sim_time,
                incident_id=incident_id,
            )
        except ReplayEngineError as exc:
            raise _http_error(exc) from exc


@router.get("/runs/{run_id}/diff", response_model=StateDiffV1)
async def get_replay_diff(
    run_id: str,
    from_sequence: FromSequenceQuery,
    to_sequence: ToSequenceQuery,
) -> StateDiffV1:
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await service.diff(
                uow,
                run_id=run_id,
                from_sequence=from_sequence,
                to_sequence=to_sequence,
            )
        except ReplayEngineError as exc:
            raise _http_error(exc) from exc


@router.get("/runs/{run_id}/snapshots", response_model=list[SnapshotManifestV1])
async def list_replay_snapshots(run_id: str) -> list[SnapshotManifestV1]:
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await service.list_snapshots(uow, run_id=run_id)


@router.post(
    "/runs/{run_id}/snapshots", response_model=SnapshotManifestV1,
    dependencies=[Depends(require_permission(PermissionV1.REPLAY_WRITE))],
)
async def create_replay_snapshot(
    run_id: str,
    request: CreateSnapshotRequestV1 | None = None,
) -> SnapshotManifestV1:
    body = request or CreateSnapshotRequestV1()
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await service.create_snapshot(
                uow,
                run_id=run_id,
                sequence=body.sequence,
                trigger_reason=body.trigger_reason,
            )
        except ReplayEngineError as exc:
            raise _http_error(exc) from exc


@router.get("/runs/{run_id}/equivalence", response_model=ReplayEquivalenceResultV1)
async def check_replay_equivalence(
    run_id: str,
    sequence: SequenceQuery = None,
) -> ReplayEquivalenceResultV1:
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await service.check_equivalence(uow, run_id=run_id, sequence=sequence)
        except ReplayEngineError as exc:
            raise _http_error(exc) from exc


@router.get("/runs/{run_id}/diagnostic", response_model=DiagnosticHarnessResponseV1)
async def replay_diagnostic_harness(
    run_id: str,
    sequence: SequenceQuery = None,
    include_equivalence: IncludeEquivalenceQuery = True,
) -> DiagnosticHarnessResponseV1:
    """Development harness payload for Phase 25 visual verification."""
    service = _replay_service()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            state = await service.reconstruct(uow, run_id=run_id, sequence=sequence)
            snapshots = await service.list_snapshots(uow, run_id=run_id)
            equivalence = None
            if include_equivalence:
                equivalence = await service.check_equivalence(
                    uow,
                    run_id=run_id,
                    sequence=sequence,
                )
        except ReplayEngineError as exc:
            raise _http_error(exc) from exc
    return DiagnosticHarnessResponseV1(
        mode="historical_replay",
        live_mutation_allowed=False,
        run_id=run_id,
        state=state,
        snapshots=snapshots,
        equivalence=equivalence,
    )
