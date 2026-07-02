"""Graph risk propagation pipeline orchestration."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.graph import GraphSnapshotV1
from aegis_contracts.risk import RiskComputeResponseV1, RiskEngineConfigV1
from aegis_contracts.versioning import RISK_COMPUTE_RESPONSE_SCHEMA_VERSION
from aegis_graph_risk import (
    DEFAULT_RISK_ENGINE_CONFIG_V1,
    deduplicate_risk_inputs,
    normalize_alert_to_risk_input,
)
from aegis_ml.risk.service import compute_graph_risk
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_incidents.risk_promotion import (
    build_risk_projection_updated_event,
    build_risk_score_computed_event,
    risk_dedup_key,
)

RISK_PIPELINE_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FB3"


async def run_risk_propagation_for_run(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    snapshot: GraphSnapshotV1,
    config: RiskEngineConfigV1 = DEFAULT_RISK_ENGINE_CONFIG_V1,
    dry_run: bool = False,
    to_sequence: int | None = None,
    incident_seed_asset_ids: list[str] | None = None,
    trace_id: str = RISK_PIPELINE_TRACE_ID,
) -> RiskComputeResponseV1:
    alerts = await uow.alerts.list_by_run(run_id)
    current_sim_time = datetime.now(tz=UTC)
    if alerts:
        latest_alert = max(alerts, key=lambda item: item.created_at)
        current_sim_time = latest_alert.created_at

    inputs = []
    for alert in alerts:
        inputs.append(normalize_alert_to_risk_input(alert, sim_time=current_sim_time))
    signals = deduplicate_risk_inputs(inputs)

    computed_at_sequence = to_sequence if to_sequence is not None else snapshot.sequence + 1
    result = compute_graph_risk(
        snapshot,
        signals,
        config,
        current_sim_time=current_sim_time,
        computed_at_sequence=computed_at_sequence,
        incident_seed_asset_ids=incident_seed_asset_ids,
    )

    events_persisted = 0
    if not dry_run:
        existing_events = await PostgresEventQueryRepository(uow.session).list_by_run(
            run_id,
            limit=100000,
        )
        max_sequence = max((event.sequence for event in existing_events), default=0)
        next_sequence = max(computed_at_sequence, max_sequence + 1)
        for score in result.scores:
            dedup = risk_dedup_key(run_id, score.asset_id, next_sequence)
            if await uow.risk_scores.exists_by_dedup_key(run_id, dedup):
                continue
            await uow.risk_scores.add(score, deduplication_key=dedup)
            await uow.append_event(
                build_risk_score_computed_event(score, sequence=next_sequence, trace_id=trace_id)
            )
            next_sequence += 1
            events_persisted += 1

        if result.projection_delta.node_updates:
            await uow.append_event(
                build_risk_projection_updated_event(
                    result.projection_delta,
                    sequence=next_sequence,
                    sim_time=current_sim_time,
                    trace_id=trace_id,
                )
            )
            events_persisted += 1

    return RiskComputeResponseV1(
        schema_version=RISK_COMPUTE_RESPONSE_SCHEMA_VERSION,
        run_id=run_id,
        algorithm_version=config.algorithm_version,
        scores_computed=len(result.scores),
        nodes_updated=len(result.projection_delta.node_updates),
        events_persisted=events_persisted,
        checksum=result.checksum,
    )
