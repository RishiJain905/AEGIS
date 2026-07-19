"""Graph risk HTTP routes."""

from __future__ import annotations

from aegis_api.auth.deps import require_permission
from aegis_api.db.session import db_session, get_db_session_maker
from aegis_contracts import PermissionV1
from aegis_contracts.risk import (
    RiskComputeRequestV1,
    RiskComputeResponseV1,
    RiskEngineConfigV1,
    RiskScoresListResponseV1,
)
from aegis_contracts.versioning import (
    RISK_COMPUTE_REQUEST_SCHEMA_VERSION,
    RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION,
)
from aegis_graph_risk import DEFAULT_RISK_ENGINE_CONFIG_V1
from aegis_incidents.risk_pipeline import run_risk_propagation_for_run
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/config", response_model=RiskEngineConfigV1)
async def get_risk_config() -> RiskEngineConfigV1:
    return DEFAULT_RISK_ENGINE_CONFIG_V1


# Persists risk scores (dry_run default False) — an investigation write action.
@router.post(
    "/compute",
    response_model=RiskComputeResponseV1,
    dependencies=[Depends(require_permission(PermissionV1.INVESTIGATION_TRIGGER))],
)
async def compute_risk(request: RiskComputeRequestV1) -> RiskComputeResponseV1:
    if request.schema_version != RISK_COMPUTE_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    async with db_session() as session:
        snapshot = await PostgresGraphSnapshotRepository(session).get_latest_for_run(
            request.run_id
        )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Graph snapshot not found for run")
    if request.to_sequence is not None:
        async with db_session() as session:
            historical = await PostgresGraphSnapshotRepository(session).get_at_sequence(
                request.run_id,
                request.to_sequence,
            )
        if historical is not None:
            snapshot = historical
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await run_risk_propagation_for_run(
            uow,
            run_id=request.run_id,
            snapshot=snapshot,
            dry_run=request.dry_run,
            to_sequence=request.to_sequence,
            incident_seed_asset_ids=request.incident_seed_asset_ids,
        )


@router.get("/scores/{run_id}", response_model=RiskScoresListResponseV1)
async def list_risk_scores(run_id: str) -> RiskScoresListResponseV1:
    async with db_session() as session:
        from aegis_persistence.repositories.postgres import PostgresRiskScoreRepository

        scores = await PostgresRiskScoreRepository(session).list_latest_by_run(run_id)
    return RiskScoresListResponseV1(
        schema_version=RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION,
        run_id=run_id,
        scores=scores,
    )
