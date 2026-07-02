"""Feature pipeline HTTP routes."""

from __future__ import annotations

from aegis_contracts.features import (
    FeatureComputeRequestV1,
    FeatureComputeResponseV1,
    FeatureParityCheckResponseV1,
    FeatureSchemaManifestV1,
)
from aegis_contracts.versioning import FEATURE_COMPUTE_REQUEST_SCHEMA_VERSION
from aegis_ml.features import (
    FEATURE_SCHEMA_MANIFEST_V1,
    build_compute_response,
    compute_features_from_events,
    run_offline_online_parity,
)
from aegis_persistence.repositories.postgres import PostgresRunRepository
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aegis_api.db.session import db_session

router = APIRouter(prefix="/api/v1/features", tags=["features"])


class FeatureParityRequestBody(BaseModel):
    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: str = Field(alias="runId", min_length=1)
    from_sequence: int | None = Field(default=None, alias="fromSequence", ge=0)
    to_sequence: int | None = Field(default=None, alias="toSequence", ge=0)

    model_config = {"populate_by_name": True}


@router.get("/schema", response_model=FeatureSchemaManifestV1)
async def get_feature_schema() -> FeatureSchemaManifestV1:
    return FEATURE_SCHEMA_MANIFEST_V1


@router.post("/compute", response_model=FeatureComputeResponseV1)
async def compute_features(request: FeatureComputeRequestV1) -> FeatureComputeResponseV1:
    if request.schema_version != FEATURE_COMPUTE_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    async with db_session() as session:
        run = await PostgresRunRepository(session).get_by_id(request.run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        events = await PostgresEventQueryRepository(session).list_by_run(
            request.run_id,
            from_sequence=request.from_sequence,
            to_sequence=request.to_sequence,
            limit=100000,
        )
    result = compute_features_from_events(run_id=request.run_id, events=events)
    return build_compute_response(result)


@router.post("/parity-check", response_model=FeatureParityCheckResponseV1)
async def parity_check(request: FeatureParityRequestBody) -> FeatureParityCheckResponseV1:
    async with db_session() as session:
        run = await PostgresRunRepository(session).get_by_id(request.run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        events = await PostgresEventQueryRepository(session).list_by_run(
            request.run_id,
            from_sequence=request.from_sequence,
            to_sequence=request.to_sequence,
            limit=100000,
        )
    return run_offline_online_parity(run_id=request.run_id, events=events)
