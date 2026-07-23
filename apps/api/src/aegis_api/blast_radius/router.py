"""Containment blast-radius preview route (Phase 7 capability loadout — decision support).

``GET /api/v1/runs/{run_id}/blast-radius?assetId=&command=`` returns the deterministic
projected collateral of a Class 2/3 containment action before the operator/approver commits.
Ownership-gated (owner-or-admin, 404/403). The projection runs over the *operator-visible*
graph: while the run is active the snapshot is fog-redacted exactly like ``GET /runs/{id}/graph``
so the preview can never leak undisclosed attacker state.
"""

from __future__ import annotations

from typing import Annotated

from aegis_contracts import (
    ApiErrorEnvelopeV1,
    AuthenticatedActorV1,
    BlastRadiusPreviewV1,
)
from aegis_contracts.errors import ContractErrorCode
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_persistence.repositories.postgres import (
    PostgresGraphSnapshotRepository,
    PostgresRunRepository,
)
from aegis_simulation.blast_radius import compute_blast_radius
from aegis_simulation.disclosure_resolver import ACTIVE_RUN_STATUSES
from aegis_simulation.graph_projection import redact_snapshot_for_disclosure
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from aegis_api.auth.deps import require_actor
from aegis_api.auth.run_authz import has_run_access
from aegis_api.db.session import get_db_session_maker
from aegis_api.runs.service import get_run_command_service

router = APIRouter(prefix="/api/v1", tags=["blast-radius"])

# Reuse the process-wide singleton so disclosure resolution can prefer a live cached runtime's
# reveal state (falling back to the persisted checkpoint), matching GET /runs/{id}/graph.
_run_service = get_run_command_service()


def _error(code: ContractErrorCode, message: str, status_code: int) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(schema_version=1, code=code.value, message=message)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(by_alias=True))


@router.get("/runs/{run_id}/blast-radius", response_model=BlastRadiusPreviewV1)
async def get_blast_radius(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    asset_id: Annotated[str, Query(alias="assetId", min_length=1)],
    command: Annotated[str, Query(min_length=1)],
) -> BlastRadiusPreviewV1 | JSONResponse:
    try:
        scenario_command = ScenarioCommandTemplateV1(command)
    except ValueError:
        return _error(
            ContractErrorCode.VALIDATION_FAILED,
            f"Unknown scenario command: {command}",
            400,
        )

    session_maker = get_db_session_maker()
    async with session_maker() as session:
        run = await PostgresRunRepository(session).get_by_id(run_id)
        if run is None:
            return _error(
                ContractErrorCode.VALIDATION_FAILED, f"Run not found: {run_id}", 404
            )
        if not has_run_access(run, actor):
            return _error(
                ContractErrorCode.VALIDATION_FAILED,
                f"Not authorized to access run: {run_id}",
                403,
            )
        snapshot = await PostgresGraphSnapshotRepository(session).get_latest_for_run(run_id)
        if snapshot is None:
            return _error(
                ContractErrorCode.VALIDATION_FAILED,
                f"Graph snapshot not found for run: {run_id}",
                404,
            )
        # Fog of war: project over the operator-visible graph while the run is active.
        if run.status in ACTIVE_RUN_STATUSES:
            disclosure = await _run_service.resolve_disclosure(session, run)
            snapshot = redact_snapshot_for_disclosure(snapshot, disclosure)

    return compute_blast_radius(
        snapshot,
        run_id=run_id,
        command=scenario_command,
        target_asset_id=asset_id,
    )
