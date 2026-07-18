"""Models HTTP routes."""

from __future__ import annotations

from pathlib import Path

from aegis_api.auth.deps import require_permission
from aegis_api.db.session import db_session, get_db_session_maker
from aegis_contracts import PermissionV1
from aegis_contracts.entities import ModelManifestV1
from aegis_contracts.models import (
    ModelScoreRequestV1,
    ModelScoreResponseV1,
    ModelVerifyArtifactRequestV1,
    ModelVerifyArtifactResponseV1,
)
from aegis_contracts.versioning import MODEL_EVALUATE_REQUEST_SCHEMA_VERSION
from aegis_incidents.model_pipeline import run_model_detection_for_events
from aegis_ml.inference.service import run_inference_for_events, to_response
from aegis_ml.models.artifact_store import DEFAULT_MODEL_DIR, load_manifest, verify_artifact
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("/manifest", response_model=ModelManifestV1)
async def get_model_manifest() -> ModelManifestV1:
    manifest_path = DEFAULT_MODEL_DIR / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Model manifest not found")
    return load_manifest(model_dir=DEFAULT_MODEL_DIR)


# Persists model detections (dry_run default False) — an investigation write action.
@router.post(
    "/score",
    response_model=ModelScoreResponseV1,
    dependencies=[Depends(require_permission(PermissionV1.INVESTIGATION_TRIGGER))],
)
async def score_run(request: ModelScoreRequestV1) -> ModelScoreResponseV1:
    if request.schema_version != MODEL_EVALUATE_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    async with db_session() as session:
        events = await PostgresEventQueryRepository(session).list_by_run(
            request.run_id,
            from_sequence=request.from_sequence,
            to_sequence=request.to_sequence,
            limit=1_000_000,
        )
    if not events:
        raise HTTPException(status_code=404, detail="No events found for run")
    if request.dry_run:
        pipeline_result = run_inference_for_events(run_id=request.run_id, events=events)
        return to_response(run_id=request.run_id, pipeline_result=pipeline_result)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await run_model_detection_for_events(
            uow,
            run_id=request.run_id,
            events=events,
            dry_run=False,
        )


# Reads arbitrary filesystem paths from the request body — a privileged/admin-only
# operation; gate behind admin:manage (no read/trigger role should reach the FS).
@router.post(
    "/verify-artifact",
    response_model=ModelVerifyArtifactResponseV1,
    dependencies=[Depends(require_permission(PermissionV1.ADMIN_MANAGE))],
)
async def verify_model_artifact(
    request: ModelVerifyArtifactRequestV1,
) -> ModelVerifyArtifactResponseV1:
    manifest_path = Path(request.manifest_path)
    artifact_path = Path(request.artifact_path) if request.artifact_path else None
    return verify_artifact(
        model_dir=manifest_path.parent,
        manifest_path=manifest_path,
        artifact_path=artifact_path,
    )
