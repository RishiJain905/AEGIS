"""Operator skill-telemetry profile assembler.

A pure, deterministic aggregation over a single operator's own terminal runs. Every
metric is derived on demand from already-persisted data (domain events, alerts,
incidents, proposals/executed actions, run scores) — there are no new tables and no
LLM in the path. All figures are heuristics and clearly non-authoritative; the coaching
lines are template-generated from the metrics.

Metric definitions (all timing is in *event-sequence units* — the run's monotonic event
sequence — an ordinal, always-present, deterministic proxy for latency that is comparable
across runs of different lengths):

* time-to-first-triage: events between the first ``alert.created`` and the first
  ``agent.task.started`` that follows it. ``None`` when no alert fired or no agent was
  tasked afterwards.
* containment latency: events between the first alert and the first *executed* Class 2/3
  (aggressive) action that follows it. ``None`` when no such containment executed.
* over-containment: of the executed Class 2/3 actions, how many targeted an asset that is
  NOT on the run's known attack path. The attack path is the set of assets named by
  ``sim.hidden_condition.revealed`` / ``sim.hidden_condition.triggered`` ground-truth
  events. When no hidden-condition event surfaced for a run, the attack path is unknown,
  so over-containment is *not judged* for that run (per-run count ``None``; the run is
  excluded from the aggregate ratio's denominator).
* false-hypothesis rate: fraction of the operator's hypotheses whose status is refuted /
  rejected / abandoned / disproven. ``None`` when no hypotheses were raised.
* score trend: per-run overall score fraction (``overallScore / maxScore``), oldest to
  newest, for the analyzed window.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import (
    CoachingLineV1,
    OperatorProfileMetricsV1,
    OperatorProfileV1,
    OperatorRunSummaryV1,
)
from aegis_contracts.entities import ActionClass
from aegis_contracts.versioning import OPERATOR_PROFILE_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork

# Cap the window so the aggregation stays cheap on demand.
DEFAULT_MAX_RUNS = 20
_TERMINAL_STATUSES = frozenset({"stopped"})
_AGGRESSIVE_CLASSES = frozenset({ActionClass.OPERATIONAL.value, ActionClass.CRITICAL.value})
_HIDDEN_CONDITION_TYPES = frozenset(
    {"sim.hidden_condition.revealed", "sim.hidden_condition.triggered"}
)
# Substrings that mark a hypothesis as ultimately wrong (case-insensitive, honest heuristic).
_REFUTED_MARKERS = ("refut", "reject", "disprov", "abandon", "withdraw", "false")


def _event_asset_id(payload: dict[str, Any], subject_id: str | None) -> str | None:
    for key in ("assetId", "asset_id", "targetAssetId", "entityId", "conditionAssetId"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    if subject_id and subject_id.startswith("asset:"):
        return subject_id
    return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


async def _summarize_run(uow: PostgresUnitOfWork, run: Any) -> OperatorRunSummaryV1:
    run_id = run.id
    events = await uow.events.list_by_run(run_id, limit=10_000)

    first_alert_seq: int | None = None
    session_role: dict[str, str] = {}
    first_task_seq: int | None = None
    first_task_session: str | None = None
    executed_seq_by_proposal: dict[str, int] = {}
    attack_path_assets: set[str] = set()

    for envelope in events:
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        etype = envelope.type
        subject_id = getattr(envelope.subject, "id", None)
        if etype == "alert.created" and first_alert_seq is None:
            first_alert_seq = envelope.sequence
        elif etype == "agent.session.started":
            sid = str(payload.get("sessionId") or subject_id or "")
            role = payload.get("role")
            if sid and isinstance(role, str):
                session_role[sid] = role
        elif etype == "agent.task.started":
            if (
                first_alert_seq is not None
                and envelope.sequence > first_alert_seq
                and first_task_seq is None
            ):
                first_task_seq = envelope.sequence
                first_task_session = str(payload.get("sessionId") or subject_id or "")
        elif etype == "action.executed":
            proposal_id = payload.get("proposalId")
            if isinstance(proposal_id, str) and proposal_id:
                # first executed event wins for a given proposal
                executed_seq_by_proposal.setdefault(proposal_id, envelope.sequence)
        elif etype in _HIDDEN_CONDITION_TYPES:
            asset = _event_asset_id(payload, subject_id)
            if asset:
                attack_path_assets.add(asset)

    time_to_first_triage: float | None = None
    if first_alert_seq is not None and first_task_seq is not None:
        time_to_first_triage = float(first_task_seq - first_alert_seq)
    first_agent_role = session_role.get(first_task_session or "")

    # Proposals + executed actions come from the incident detail (authoritative target
    # asset + action class), correlated to their executed sequence via the events above.
    proposals_by_id: dict[str, Any] = {}
    executed_proposal_ids: set[str] = set()
    hypothesis_statuses: list[str] = []
    incidents = await uow.incidents.list_by_run(run_id)
    for incident in incidents:
        detail = await uow.investigation.get_detail(incident.id, run_id)
        for prop in detail.proposals:
            proposals_by_id[prop.id] = prop
        for action in detail.executed_actions:
            executed_proposal_ids.add(action.proposal_id)
        for hyp in detail.hypotheses:
            hypothesis_statuses.append(str(getattr(hyp, "status", "") or ""))

    aggressive_executed: list[tuple[int | None, str | None, str]] = []
    for proposal_id in executed_proposal_ids:
        matched = proposals_by_id.get(proposal_id)
        if matched is None:
            continue
        action_class = (
            matched.action_class.value
            if hasattr(matched.action_class, "value")
            else str(matched.action_class)
        )
        if action_class not in _AGGRESSIVE_CLASSES:
            continue
        seq = executed_seq_by_proposal.get(proposal_id)
        target = getattr(matched, "target_asset_id", None)
        aggressive_executed.append((seq, target, action_class))

    aggressive_action_count = len(aggressive_executed)

    containment_latency: float | None = None
    if first_alert_seq is not None:
        post_alert_seqs = [
            seq
            for seq, _target, _cls in aggressive_executed
            if seq is not None and seq > first_alert_seq
        ]
        if post_alert_seqs:
            containment_latency = float(min(post_alert_seqs) - first_alert_seq)

    over_containment_count: int | None = None
    if attack_path_assets and aggressive_executed:
        over_containment_count = sum(
            1
            for _seq, target, _cls in aggressive_executed
            if target is None or target not in attack_path_assets
        )

    hypothesis_count = len(hypothesis_statuses)
    false_hypothesis_count = sum(
        1
        for status in hypothesis_statuses
        if any(marker in status.lower() for marker in _REFUTED_MARKERS)
    )

    latest_score = await uow.run_scores.get_latest_for_run(run_id)
    score_fraction: float | None = None
    if latest_score is not None and latest_score.max_score > 0:
        score_fraction = max(0.0, min(1.0, latest_score.overall_score / latest_score.max_score))

    return OperatorRunSummaryV1(
        run_id=run_id,
        scenario_id=_scenario_id_of(run),
        seed=run.seed,
        status=str(run.status),
        started_at=_isoformat(run.started_at),
        score=score_fraction,
        time_to_first_triage=time_to_first_triage,
        containment_latency=containment_latency,
        first_agent_role=first_agent_role,
        aggressive_action_count=aggressive_action_count,
        over_containment_count=over_containment_count,
        hypothesis_count=hypothesis_count,
        false_hypothesis_count=false_hypothesis_count,
    )


def _scenario_id_of(run: Any) -> str:
    version_id = str(getattr(run, "scenario_version_id", "") or "")
    return version_id or "scenario:unknown"


def _isoformat(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _build_metrics(summaries: list[OperatorRunSummaryV1]) -> OperatorProfileMetricsV1:
    triage = [s.time_to_first_triage for s in summaries if s.time_to_first_triage is not None]
    containment = [s.containment_latency for s in summaries if s.containment_latency is not None]
    scores = [s.score for s in summaries if s.score is not None]

    # Over-containment ratio: over runs where the attack path is known.
    judged = [s for s in summaries if s.over_containment_count is not None]
    total_aggressive = sum(s.aggressive_action_count for s in judged)
    total_over = sum(s.over_containment_count or 0 for s in judged)
    over_ratio = (total_over / total_aggressive) if total_aggressive > 0 else None

    total_hyp = sum(s.hypothesis_count for s in summaries)
    total_false = sum(s.false_hypothesis_count for s in summaries)
    false_rate = (total_false / total_hyp) if total_hyp > 0 else None

    return OperatorProfileMetricsV1(
        runs_analyzed=len(summaries),
        avg_time_to_first_triage=_mean(triage),
        avg_containment_latency=_mean(containment),
        over_containment_ratio=over_ratio,
        false_hypothesis_rate=false_rate,
        avg_score=_mean(scores),
        score_trend=[s.score for s in summaries if s.score is not None],
    )


def _build_coaching(
    summaries: list[OperatorRunSummaryV1], metrics: OperatorProfileMetricsV1
) -> list[CoachingLineV1]:
    """Deterministic, template-generated coaching from the metrics. Order is stable."""
    lines: list[CoachingLineV1] = []

    # 1. TRACE-first speed advantage.
    trace_first = [
        s.containment_latency
        for s in summaries
        if s.first_agent_role == "TRACE" and s.containment_latency is not None
    ]
    overall = [s.containment_latency for s in summaries if s.containment_latency is not None]
    trace_avg = _mean(trace_first)
    overall_avg = _mean(overall)
    has_trace_edge = (
        trace_avg is not None
        and overall_avg is not None
        and overall_avg > 0
        and len(trace_first) >= 2
        and trace_avg < overall_avg
    )
    if has_trace_edge:
        assert trace_avg is not None and overall_avg is not None  # narrowed by has_trace_edge
        pct = round((1.0 - trace_avg / overall_avg) * 100)
        if pct >= 10:
            lines.append(
                CoachingLineV1(
                    id="trace-first-speed",
                    tone="reinforce",
                    message=(
                        f"You contain {pct}% faster than your average when you task "
                        "TRACE first — keep leading with TRACE."
                    ),
                )
            )

    # 2. Over-containment on off-path assets.
    judged = [s for s in summaries if s.over_containment_count is not None]
    over_runs = [s for s in judged if (s.over_containment_count or 0) > 0]
    if metrics.over_containment_ratio is not None and metrics.over_containment_ratio >= 0.4:
        lines.append(
            CoachingLineV1(
                id="over-containment",
                tone="improve",
                message=(
                    f"{len(over_runs)} of your last {len(judged)} judged runs had aggressive "
                    "containments that hit assets never part of the attack — consider one more "
                    "evidence pass before a Class 2/3 action."
                ),
            )
        )

    # 3. False-hypothesis rate.
    if metrics.false_hypothesis_rate is not None and metrics.false_hypothesis_rate >= 0.5:
        pct = round(metrics.false_hypothesis_rate * 100)
        lines.append(
            CoachingLineV1(
                id="false-hypothesis",
                tone="improve",
                message=(
                    f"{pct}% of your hypotheses were later refuted — gather corroborating "
                    "evidence before committing to a leading theory."
                ),
            )
        )

    # 4. Score trend.
    trend = metrics.score_trend
    if len(trend) >= 3 and trend[-1] > trend[0]:
        first_pct = round(trend[0] * 100)
        last_pct = round(trend[-1] * 100)
        lines.append(
            CoachingLineV1(
                id="score-trend-up",
                tone="reinforce",
                message=(
                    "Your scores are trending up across recent runs "
                    f"({first_pct}% to {last_pct}%) — the reps are paying off."
                ),
            )
        )

    # 5. Thin-data caveat (always honest about small samples).
    if metrics.runs_analyzed < 3:
        lines.append(
            CoachingLineV1(
                id="thin-data",
                tone="neutral",
                message=(
                    f"Only {metrics.runs_analyzed} completed run(s) analyzed so far — patterns "
                    "firm up as you finish more engagements."
                ),
            )
        )

    return lines


async def assemble_operator_profile(
    uow: PostgresUnitOfWork,
    *,
    owner_user_id: str,
    max_runs: int = DEFAULT_MAX_RUNS,
) -> OperatorProfileV1:
    """Assemble the owner's cross-run skill-telemetry profile (newest window, oldest→newest)."""
    owned = await uow.runs.list_for_owner(owner_user_id)
    terminal = [run for run in owned if str(run.status) in _TERMINAL_STATUSES]
    # ``list_for_owner`` returns newest-first; take the window, then order oldest→newest so
    # the trend and per-run list read chronologically.
    window = list(reversed(terminal[:max_runs]))

    summaries = [await _summarize_run(uow, run) for run in window]
    metrics = _build_metrics(summaries)
    coaching = _build_coaching(summaries, metrics)

    return OperatorProfileV1(
        schema_version=OPERATOR_PROFILE_SCHEMA_VERSION,
        owner_user_id=owner_user_id,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        metrics=metrics,
        runs=summaries,
        coaching=coaching,
    )
