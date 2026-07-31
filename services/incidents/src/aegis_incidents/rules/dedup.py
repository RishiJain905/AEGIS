"""Duplicate suppression and cooldown handling."""

from __future__ import annotations

from datetime import datetime

from aegis_contracts.detection import AlertCandidateV1, DetectionRuleV1

from aegis_incidents.rules.state import DetectionRunState

SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def build_deduplication_key(
    *,
    run_id: str,
    rule_id: str,
    entity_id: str,
    window_start_epoch: int,
) -> str:
    return f"{run_id}:{rule_id}:{entity_id}:{window_start_epoch}"


def parse_window_start_epoch(window_key: str) -> int:
    parts = window_key.split(":")
    return int(parts[-1])


def should_suppress_candidate(
    candidate: AlertCandidateV1,
    rule: DetectionRuleV1,
    state: DetectionRunState,
    *,
    existing_dedup_keys: set[str],
    now_sim_time: datetime,
) -> tuple[bool, str]:
    if candidate.deduplication_key in existing_dedup_keys:
        return True, "duplicate_authoritative_alert"
    if candidate.deduplication_key in state.emitted_dedup_keys:
        return True, "duplicate_in_run"

    for prior_key in state.emitted_dedup_keys:
        prior_parts = prior_key.split(":")
        if len(prior_parts) != 4:
            continue
        prior_rule, prior_entity, prior_window = prior_parts[1], prior_parts[2], int(prior_parts[3])
        if prior_rule != candidate.rule_id or prior_entity != candidate.entity_id:
            continue
        if now_sim_time.timestamp() - prior_window < rule.cooldown_sim_seconds:
            return True, "cooldown_active"

    if rule.suppression_group:
        prior = state.last_alert_by_group.get(
            (rule.suppression_group, candidate.entity_id)
        )
        if prior is not None:
            prior_severity, prior_time = prior
            prior_rank = SEVERITY_RANK.get(prior_severity, 0)
            current_rank = SEVERITY_RANK.get(candidate.severity, 0)
            elapsed = (now_sim_time - prior_time).total_seconds()
            if elapsed < rule.cooldown_sim_seconds and current_rank <= prior_rank:
                return True, "suppression_group_active"

    return False, ""


def record_emitted_candidate(
    candidate: AlertCandidateV1,
    rule: DetectionRuleV1,
    state: DetectionRunState,
    *,
    now_sim_time: datetime,
) -> None:
    state.emitted_dedup_keys.add(candidate.deduplication_key)
    if rule.suppression_group:
        state.last_alert_by_group[(rule.suppression_group, candidate.entity_id)] = (
            candidate.severity,
            now_sim_time,
        )
    state.alert_timestamps.append((now_sim_time, candidate.rule_id, candidate.entity_id))
