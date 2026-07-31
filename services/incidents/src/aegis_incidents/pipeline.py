"""Detection pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from aegis_contracts import DomainEventEnvelopeV1
from aegis_contracts.detection import (
    AlertCandidateV1,
    DetectionEvaluateResponseV1,
    DetectionRuleRegistryV1,
    RuleEvaluationStatus,
    RuleEvaluationV1,
    StatisticalBaselineV1,
)
from aegis_contracts.versioning import DETECTION_EVALUATE_RESPONSE_SCHEMA_VERSION
from aegis_ml.features import compute_features_from_events
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_incidents.correlation import open_correlated_incidents
from aegis_incidents.promotion import build_alert_created_event, candidate_to_alert
from aegis_incidents.rules.dedup import record_emitted_candidate, should_suppress_candidate
from aegis_incidents.rules.evaluator import evaluate_vectors
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1
from aegis_incidents.rules.state import DetectionRunState

DETECTION_PIPELINE_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX"


@dataclass
class DetectionPipelineResult:
    evaluations: list[RuleEvaluationV1] = field(default_factory=list)
    accepted_candidates: list[AlertCandidateV1] = field(default_factory=list)
    alerts_suppressed: int = 0
    deterministic_checksum: str = ""


def _checksum_evaluations(evaluations: list[RuleEvaluationV1]) -> str:
    payload = [
        evaluation.model_dump(mode="json", by_alias=True, exclude_none=True)
        for evaluation in evaluations
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def evaluate_features_offline(
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
    registry: DetectionRuleRegistryV1 = DETECTION_RULE_REGISTRY_V1,
    baselines: StatisticalBaselineV1 | None = None,
    existing_dedup_keys: set[str] | None = None,
) -> DetectionPipelineResult:
    feature_result = compute_features_from_events(run_id=run_id, events=events)
    run_state = DetectionRunState()
    dedup_keys = set(existing_dedup_keys or set())
    evaluations = evaluate_vectors(
        feature_result.vectors,
        run_id=run_id,
        rules=registry.rules,
        baselines=baselines,
        state=run_state,
    )
    rules_by_id = {rule.rule_id: rule for rule in registry.rules}
    accepted: list[AlertCandidateV1] = []
    suppressed = 0

    for evaluation in evaluations:
        if evaluation.status != RuleEvaluationStatus.FIRED or evaluation.candidate is None:
            continue
        candidate = evaluation.candidate
        rule = rules_by_id[candidate.rule_id]
        suppressed_flag, _reason = should_suppress_candidate(
            candidate,
            rule,
            run_state,
            existing_dedup_keys=dedup_keys,
            now_sim_time=candidate.evidence.sim_time_end,
        )
        if suppressed_flag:
            suppressed += 1
            continue
        accepted.append(candidate)
        record_emitted_candidate(
            candidate,
            rule,
            run_state,
            now_sim_time=candidate.evidence.sim_time_end,
        )

    return DetectionPipelineResult(
        evaluations=evaluations,
        accepted_candidates=accepted,
        alerts_suppressed=suppressed,
        deterministic_checksum=_checksum_evaluations(evaluations),
    )


async def persist_detection_candidates(
    uow: PostgresUnitOfWork,
    candidates: list[AlertCandidateV1],
    *,
    events: list[DomainEventEnvelopeV1],
    trace_id: str,
) -> int:
    if not candidates:
        return 0
    max_sequence = max((event.sequence for event in events), default=0)
    persisted = 0
    next_sequence = max_sequence + 1
    for candidate in candidates:
        if await uow.alerts.exists_by_dedup_key(candidate.run_id, candidate.deduplication_key):
            continue
        alert = candidate_to_alert(candidate)
        await uow.alerts.add(alert)
        event = build_alert_created_event(
            alert,
            sequence=next_sequence,
            sim_time=candidate.evidence.sim_time_end,
            trace_id=trace_id,
        )
        await uow.append_event(event)
        next_sequence += 1
        persisted += 1
    return persisted


async def run_detection_for_events(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
    baselines: StatisticalBaselineV1 | None = None,
    dry_run: bool = False,
    trace_id: str = DETECTION_PIPELINE_TRACE_ID,
) -> DetectionEvaluateResponseV1:
    existing_keys = await uow.alerts.list_dedup_keys_for_run(run_id)
    pipeline_result = evaluate_features_offline(
        run_id=run_id,
        events=events,
        baselines=baselines,
        existing_dedup_keys=existing_keys,
    )
    persisted = 0
    if not dry_run:
        persisted = await persist_detection_candidates(
            uow,
            pipeline_result.accepted_candidates,
            events=events,
            trace_id=trace_id,
        )
        # Correlation runs on every evaluation, not only when this pass persisted an
        # alert: a case can also become warranted because the simulation compromised an
        # asset that was already alerting. It is idempotent (deterministic incident ids,
        # dedupe against the run's open cases), so a re-scan opens nothing twice.
        await open_correlated_incidents(
            uow,
            run_id=run_id,
            events=events,
            trace_id=trace_id,
        )

    return DetectionEvaluateResponseV1(
        schema_version=DETECTION_EVALUATE_RESPONSE_SCHEMA_VERSION,
        run_id=run_id,
        candidates_emitted=len(pipeline_result.accepted_candidates),
        alerts_persisted=persisted,
        alerts_suppressed=pipeline_result.alerts_suppressed,
        evaluations=pipeline_result.evaluations,
        deterministic_checksum=pipeline_result.deterministic_checksum,
    )
