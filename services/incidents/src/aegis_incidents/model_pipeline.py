"""Model anomaly detection pipeline orchestration."""

from __future__ import annotations

from aegis_contracts import DomainEventEnvelopeV1
from aegis_contracts.models import ModelScoreResponseV1
from aegis_ml.inference.service import run_inference_for_events, to_response
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_incidents.model_promotion import (
    build_model_alert_created_event,
    build_model_score_recorded_event,
    inference_to_alert,
    inference_to_model_score,
)

MODEL_PIPELINE_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FB2"


async def run_model_detection_for_events(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
    dry_run: bool = False,
    trace_id: str = MODEL_PIPELINE_TRACE_ID,
) -> ModelScoreResponseV1:
    existing_keys = await uow.alerts.list_dedup_keys_for_run(run_id)
    pipeline_result = run_inference_for_events(
        run_id=run_id,
        events=events,
        existing_dedup_keys=existing_keys,
    )
    anomalies = [item for item in pipeline_result.results if item.is_anomaly]
    suppressed = len(pipeline_result.results) - len(anomalies)
    persisted_alerts = 0
    if not dry_run and not pipeline_result.fallback.active:
        max_sequence = max((event.sequence for event in events), default=0)
        next_sequence = max_sequence + 1
        for result in anomalies:
            if await uow.alerts.exists_by_dedup_key(run_id, result.deduplication_key):
                continue
            alert = inference_to_alert(result, run_id=run_id)
            await uow.alerts.add(alert)
            score = inference_to_model_score(result)
            await uow.models.add_score(score, deduplication_key=result.deduplication_key)
            await uow.append_event(
                build_model_score_recorded_event(
                    score,
                    run_id=run_id,
                    sequence=next_sequence,
                    sim_time=result.explanation.source_window.sim_time_end,
                    trace_id=trace_id,
                )
            )
            next_sequence += 1
            await uow.append_event(
                build_model_alert_created_event(
                    alert,
                    sequence=next_sequence,
                    sim_time=result.explanation.source_window.sim_time_end,
                    trace_id=trace_id,
                )
            )
            next_sequence += 1
            persisted_alerts += 1

    return to_response(
        run_id=run_id,
        pipeline_result=pipeline_result,
        alerts_persisted=persisted_alerts,
        scores_suppressed=suppressed,
    )
