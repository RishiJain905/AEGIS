"""Detection HTTP routes."""

from __future__ import annotations

from aegis_api.auth.deps import require_permission
from aegis_api.db.session import db_session, get_db_session_maker
from aegis_contracts import PermissionV1
from aegis_contracts.detection import (
    DetectionEvaluateRequestV1,
    DetectionEvaluateResponseV1,
    DetectionRuleRegistryV1,
    StatisticalBaselineManifestV1,
)
from aegis_contracts.versioning import DETECTION_EVALUATE_REQUEST_SCHEMA_VERSION
from aegis_incidents.pipeline import run_detection_for_events
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1
from aegis_ml.baselines.store import DEFAULT_BASELINE_DIR, load_baseline_manifest
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/v1/detection", tags=["detection"])


@router.get("/rules", response_model=DetectionRuleRegistryV1)
async def get_detection_rules() -> DetectionRuleRegistryV1:
    return DETECTION_RULE_REGISTRY_V1


@router.get("/baselines", response_model=StatisticalBaselineManifestV1)
async def get_baseline_manifest() -> StatisticalBaselineManifestV1:
    manifest_path = DEFAULT_BASELINE_DIR / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Baseline manifest not found")
    return load_baseline_manifest()


# Persists alerts/incidents (dry_run defaults False) — an investigation write action;
# reuse investigation:trigger so a read-only VIEWER cannot mutate authoritative state.
@router.post(
    "/evaluate",
    response_model=DetectionEvaluateResponseV1,
    dependencies=[Depends(require_permission(PermissionV1.INVESTIGATION_TRIGGER))],
)
async def evaluate_detection(request: DetectionEvaluateRequestV1) -> DetectionEvaluateResponseV1:
    if request.schema_version != DETECTION_EVALUATE_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    baselines = None
    baseline_path = DEFAULT_BASELINE_DIR / "baseline.json"
    if baseline_path.exists():
        from aegis_ml.baselines.store import load_baseline

        baselines = load_baseline()
    async with db_session() as session:
        events = await PostgresEventQueryRepository(session).list_by_run(
            request.run_id,
            from_sequence=request.from_sequence,
            to_sequence=request.to_sequence,
            limit=1_000_000,
        )
    if not events:
        raise HTTPException(status_code=404, detail="No events found for run")
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await run_detection_for_events(
            uow,
            run_id=request.run_id,
            events=events,
            baselines=baselines,
            dry_run=request.dry_run,
        )
