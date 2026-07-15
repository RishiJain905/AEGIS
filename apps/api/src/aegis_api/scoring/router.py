"""Phase 29 scoring and after-action HTTP routes."""

from __future__ import annotations

from pathlib import Path

from aegis_contracts import PermissionV1
from aegis_contracts.scoring import (
    AfterActionViewModelV1,
    RunComparisonV1,
    RunScoreV1,
    ScoreErrorCode,
    ScoreExportFormatV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_scoring.errors import ScoringError
from aegis_scoring.service import ScoringService
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from aegis_api.auth.deps import require_permission
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1", tags=["scoring"])
_scoring_service = ScoringService()
_SCENARIOS_ROOT = Path("scenarios")


def _http_status(code: ScoreErrorCode) -> int:
    if code in {
        ScoreErrorCode.SCORE_NOT_FOUND,
    }:
        return 404
    if code in {
        ScoreErrorCode.SCORE_INCOMPLETE_RUN,
        ScoreErrorCode.SCORE_RUBRIC_MISSING,
        ScoreErrorCode.SCORE_RUBRIC_INCOMPATIBLE,
        ScoreErrorCode.SCORE_INPUT_TAMPERED,
        ScoreErrorCode.SCORE_CHECKSUM_MISMATCH,
        ScoreErrorCode.SCORE_COMPARISON_INVALID,
        ScoreErrorCode.SCORE_VALIDATION_FAILED,
    }:
        return 409
    return 400


@router.post(
    "/runs/{run_id}/score", response_model=RunScoreV1,
    dependencies=[Depends(require_permission(PermissionV1.SCORING_COMPUTE))],
)
async def score_run(run_id: str) -> RunScoreV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await _scoring_service.score_run(
                uow,
                run_id=run_id,
                scenarios_root=_SCENARIOS_ROOT,
            )
        except ScoringError as exc:
            raise HTTPException(
                status_code=_http_status(exc.code),
                detail={"code": exc.code.value, "message": exc.message, "details": exc.details},
            ) from exc


@router.get("/runs/{run_id}/score", response_model=RunScoreV1)
async def get_run_score(run_id: str) -> RunScoreV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await _scoring_service.get_score(uow, run_id=run_id)
        except ScoringError as exc:
            raise HTTPException(
                status_code=_http_status(exc.code),
                detail={"code": exc.code.value, "message": exc.message, "details": exc.details},
            ) from exc


@router.get("/runs/{run_id}/after-action", response_model=AfterActionViewModelV1)
async def get_after_action(run_id: str) -> AfterActionViewModelV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await _scoring_service.get_after_action(
                uow,
                run_id=run_id,
                scenarios_root=_SCENARIOS_ROOT,
            )
        except ScoringError as exc:
            raise HTTPException(
                status_code=_http_status(exc.code),
                detail={"code": exc.code.value, "message": exc.message, "details": exc.details},
            ) from exc


@router.get(
    "/runs/{run_id}/score/export/{export_format}",
    dependencies=[Depends(require_permission(PermissionV1.SCORING_EXPORT))],
)
async def export_run_score(run_id: str, export_format: ScoreExportFormatV1) -> Response:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            artifact, content = await _scoring_service.export_score(
                uow,
                run_id=run_id,
                export_format=export_format,
            )
        except ScoringError as exc:
            raise HTTPException(
                status_code=_http_status(exc.code),
                detail={"code": exc.code.value, "message": exc.message, "details": exc.details},
            ) from exc
    media = "application/json" if export_format == ScoreExportFormatV1.JSON else "text/markdown"
    return Response(
        content=content,
        media_type=media,
        headers={
            "X-AEGIS-Score-Id": artifact.score_id,
            "X-AEGIS-Score-Integrity": artifact.integrity_checksum,
            "X-AEGIS-Score-Content-Checksum": artifact.content_checksum,
            "X-AEGIS-Grading-Engine": artifact.grading_engine_version,
            "X-AEGIS-Rubric-Version": artifact.rubric_version,
            "X-AEGIS-Scenario-Version": artifact.scenario_version,
        },
    )


@router.get("/runs/score-comparison", response_model=RunComparisonV1)
async def compare_run_scores(
    left: str = Query(..., min_length=1),
    right: str = Query(..., min_length=1),
) -> RunComparisonV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await _scoring_service.compare_runs(
                uow,
                left_run_id=left,
                right_run_id=right,
            )
        except ScoringError as exc:
            raise HTTPException(
                status_code=_http_status(exc.code),
                detail={"code": exc.code.value, "message": exc.message, "details": exc.details},
            ) from exc
