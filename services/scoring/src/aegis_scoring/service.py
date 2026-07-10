"""Scoring orchestration service with idempotent persistence."""

from __future__ import annotations

from pathlib import Path

from aegis_contracts.scoring import (
    AfterActionViewModelV1,
    RunComparisonV1,
    RunScoreV1,
    ScoreErrorCode,
    ScoreExportArtifactV1,
    ScoreExportFormatV1,
)
from aegis_contracts.versioning import RUN_COMPARISON_SCORE_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_scoring.assembler import assemble_scoring_facts
from aegis_scoring.engine import compute_run_score
from aegis_scoring.errors import ScoringError
from aegis_scoring.export import render_score_export
from aegis_scoring.view_model import build_after_action_view_model


class ScoringService:
    async def score_run(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        scenarios_root: Path | None = None,
        incident_id: str | None = None,
        force: bool = False,
    ) -> RunScoreV1:
        facts = await assemble_scoring_facts(
            uow,
            run_id=run_id,
            scenarios_root=scenarios_root,
            incident_id=incident_id,
        )
        score = compute_run_score(facts)

        existing = await uow.run_scores.get_by_fingerprint(score.provenance.fingerprint)
        if existing is not None and not force:
            return existing

        # Also return latest if same fingerprint already stored for run
        latest = await uow.run_scores.get_latest_for_run(run_id)
        if latest is not None and latest.provenance.fingerprint == score.provenance.fingerprint:
            return latest

        await uow.run_scores.add(score)
        return score

    async def get_score(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        score_id: str | None = None,
    ) -> RunScoreV1:
        if score_id is not None:
            score = await uow.run_scores.get_by_id(score_id)
            if score is None or score.run_id != run_id:
                raise ScoringError(
                    code=ScoreErrorCode.SCORE_NOT_FOUND,
                    message=f"Score not found: {score_id}",
                )
            return score
        score = await uow.run_scores.get_latest_for_run(run_id)
        if score is None:
            raise ScoringError(
                code=ScoreErrorCode.SCORE_NOT_FOUND,
                message=f"No score for run: {run_id}",
            )
        return score

    async def get_after_action(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        scenarios_root: Path | None = None,
    ) -> AfterActionViewModelV1:
        try:
            score = await self.get_score(uow, run_id=run_id)
        except ScoringError:
            score = await self.score_run(uow, run_id=run_id, scenarios_root=scenarios_root)
        facts = await assemble_scoring_facts(uow, run_id=run_id, scenarios_root=scenarios_root)
        return build_after_action_view_model(facts, score)

    async def export_score(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        export_format: ScoreExportFormatV1,
    ) -> tuple[ScoreExportArtifactV1, bytes]:
        score = await self.get_score(uow, run_id=run_id)
        content, artifact = render_score_export(score, export_format)
        return artifact, content

    async def compare_runs(
        self,
        uow: PostgresUnitOfWork,
        *,
        left_run_id: str,
        right_run_id: str,
    ) -> RunComparisonV1:
        left = await self.get_score(uow, run_id=left_run_id)
        right = await self.get_score(uow, run_id=right_run_id)
        left_by_id = {c.criterion_id: c for c in left.components}
        right_by_id = {c.criterion_id: c for c in right.components}
        criterion_ids = sorted(set(left_by_id) | set(right_by_id))
        deltas = []
        for cid in criterion_ids:
            left_raw = left_by_id[cid].raw_score if cid in left_by_id else 0.0
            right_raw = right_by_id[cid].raw_score if cid in right_by_id else 0.0
            deltas.append(
                {
                    "criterionId": cid,
                    "leftRawScore": left_raw,
                    "rightRawScore": right_raw,
                    "delta": round(right_raw - left_raw, 4),
                }
            )
        return RunComparisonV1.model_validate(
            {
                "schemaVersion": RUN_COMPARISON_SCORE_SCHEMA_VERSION,
                "leftRunId": left.run_id,
                "rightRunId": right.run_id,
                "leftScoreId": left.score_id,
                "rightScoreId": right.score_id,
                "leftOverallScore": left.overall_score,
                "rightOverallScore": right.overall_score,
                "overallDelta": round(right.overall_score - left.overall_score, 4),
                "componentDeltas": deltas,
                "gradingEngineVersion": left.provenance.grading_engine_version,
            }
        )
