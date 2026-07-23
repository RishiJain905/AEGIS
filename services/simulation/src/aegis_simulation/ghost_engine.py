"""Ghost branch — deterministic, isolated post-run counterfactual replay engine.

The flagship after-action capability. Given a terminal run, the operator picks a real
decision point (an executed containment, or an "inaction window") and asks the engine to
re-simulate the scenario with a different call. The engine returns the REAL alternate
timeline, not speculation.

Isolation guarantees (non-negotiable):

* The engine only ever READS from the unit of work (events, run row, stored score). It
  never appends events, writes snapshots, raises alerts, or touches the outbox.
* Every re-simulation runs on a fresh, throwaway :class:`SimulationRuntime` built here and
  never inserted into any :class:`RunCommandService.runtime_cache`. The live run's cached
  runtime, event stream, and graph snapshots are untouched.

Determinism: the result is a pure function of the persisted pre-fork event stream, the run
seed, the scenario manifest, and the alternate decision. The same request twice yields an
identical ``result_hash``. No wall-clock, no global RNG.

How a fork works: a fresh runtime is deterministically advanced to the decision point by
replaying the persisted simulation events with ``sequence < fork_sequence`` (the same
replay path restart-recovery uses), preserving every real event — including the operator's
*earlier* real actions — up to the fork. The alternate decision is then applied in memory
and the runtime is stepped to the scenario horizon.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aegis_contracts import (
    ActorRef,
    ActorType,
    DomainEventEnvelopeV1,
    GhostAssetDiffV1,
    GhostBranchModeV1,
    GhostBranchRequestV1,
    GhostBranchResultV1,
    GhostDecisionKindV1,
    GhostDecisionPointsV1,
    GhostDecisionPointV1,
    GhostOutcomeV1,
    GhostTimelineBeatV1,
    SimulationCommandType,
    SimulationCommandV1,
)
from aegis_contracts.ghost import GhostAssetStatusV1
from aegis_contracts.simulation import SimulationRunStatus
from aegis_contracts.versioning import (
    GHOST_BRANCH_RESULT_SCHEMA_VERSION,
    GHOST_DECISION_POINT_SCHEMA_VERSION,
    GHOST_DECISION_POINTS_SCHEMA_VERSION,
    SIMULATION_COMMAND_SCHEMA_VERSION,
)
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy.commands import (
    COMMAND_STATUS_MAP,
    COMMAND_TO_ACTION_CLASS,
    STATUS_TO_COMMAND,
)
from aegis_simulation_domain import SimulationEngine, SimulationError
from aegis_simulation_domain.runtime import SimulationRuntime

from aegis_simulation.run_command_service import RunCommandService, _is_sim_event

# A single ghost re-simulation is bounded well past any scenario's scheduled-event count,
# so stepping terminates on queue exhaustion in practice; the cap only guards a runaway.
GHOST_MAX_STEPS = 1000

# Terminal statuses used to summarize an outcome. These are presentation categories for the
# outcome cards; the load-bearing comparison is the per-asset ``asset_diffs``.
_ADVERSARY_STATUSES: frozenset[str] = frozenset({"compromised", "suspicious"})
_CONTAINED_STATUSES: frozenset[str] = frozenset(
    {"isolated", "access_restricted", "credentials_revoked", "contained", "rolling_back",
     "restarting"}
)
_BREACH_STATUSES: frozenset[str] = frozenset({"compromised"})

# Adversary/simulation event types that make up the attacker-lane ghost timeline.
_TIMELINE_KINDS: dict[str, str] = {
    "sim.hidden_condition.triggered": "condition_triggered",
    "sim.hidden_condition.revealed": "condition_revealed",
    "sim.branch.selected": "branch_selected",
}


class GhostBranchError(Exception):
    """Ghost branch could not be computed (bad decision ref, non-terminal run, etc.)."""

    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass
class _DecisionPlan:
    """Resolved fork instructions for one ghost request."""

    fork_sequence: int
    divergence_sim_time: datetime
    # The command to inject and its target (None = do nothing / omit the real action).
    command: Any | None
    target_asset_id: str | None
    # When set, inject the command once the clock reaches this sim_time (SHIFT later);
    # otherwise the command is applied immediately at the fork.
    apply_at: datetime | None


@dataclass
class GhostBranchEngine:
    """Reads persisted run history and produces isolated counterfactual results."""

    workspace_root: Path

    def __post_init__(self) -> None:
        # A private RunCommandService reused only for package resolution and the shared
        # deterministic replay helper. Its runtime_cache is never populated by this engine,
        # so it cannot perturb the live run's cached runtime.
        self._rcs = RunCommandService(workspace_root=self.workspace_root)

    # -- decision-point enumeration -------------------------------------------------

    async def enumerate_decision_points(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> GhostDecisionPointsV1:
        run = await uow.runs.get_by_id(run_id)
        if run is None:
            raise GhostBranchError(
                code="RUN_NOT_FOUND", message=f"Run not found: {run_id}", status_code=404
            )
        sim_events = await self._load_sim_events(uow, run_id)
        points = _enumerate_decision_points(sim_events)
        return GhostDecisionPointsV1(
            schema_version=GHOST_DECISION_POINTS_SCHEMA_VERSION,
            run_id=run_id,
            decision_points=points,
        )

    # -- counterfactual run ---------------------------------------------------------

    async def run_ghost(
        self, uow: PostgresUnitOfWork, run_id: str, request: GhostBranchRequestV1
    ) -> GhostBranchResultV1:
        run = await uow.runs.get_by_id(run_id)
        if run is None:
            raise GhostBranchError(
                code="RUN_NOT_FOUND", message=f"Run not found: {run_id}", status_code=404
            )
        sim_events = await self._load_sim_events(uow, run_id)
        real_score: float | None = None
        stored = await uow.run_scores.get_latest_for_run(run_id)
        if stored is not None:
            real_score = float(stored.overall_score)
        return self.compute_ghost(
            run_id=run_id,
            seed=run.seed,
            scenario_version_id=run.scenario_version_id,
            sim_events=sim_events,
            request=request,
            real_overall_score=real_score,
        )

    def compute_ghost(
        self,
        *,
        run_id: str,
        seed: int,
        scenario_version_id: str,
        sim_events: list[DomainEventEnvelopeV1],
        request: GhostBranchRequestV1,
        real_overall_score: float | None = None,
    ) -> GhostBranchResultV1:
        """Pure counterfactual computation — no I/O, no DB, no writes.

        Deterministic in its inputs, so a determinism test can call it twice offline and
        assert identical ``result_hash``. ``run_ghost`` is the thin uow-bound wrapper.
        """
        decision_points = _enumerate_decision_points(sim_events)
        decision = next(
            (dp for dp in decision_points if dp.decision_ref == request.decision_ref), None
        )
        if decision is None:
            raise GhostBranchError(
                code="DECISION_NOT_FOUND",
                message=f"Unknown decision ref: {request.decision_ref}",
                status_code=404,
            )
        plan = _plan_fork(decision, request, sim_events)

        # Ghost timeline: fork a throwaway runtime, apply the alternate, step to horizon.
        ghost_runtime = self._build_runtime(run_id, seed, scenario_version_id)
        pre_fork = [e for e in sim_events if e.sequence < plan.fork_sequence]
        self._rcs._replay_events(ghost_runtime, pre_fork)  # noqa: SLF001 (shared helper)
        _ensure_running(ghost_runtime)

        emitted: list[DomainEventEnvelopeV1] = []
        if plan.command is not None and plan.apply_at is None:
            emitted.extend(_apply_command(ghost_runtime, plan.command, plan.target_asset_id))
        horizon_events, steps = _step_to_horizon(
            ghost_runtime,
            pending_command=plan.command if plan.apply_at is not None else None,
            target_asset_id=plan.target_asset_id,
            apply_at=plan.apply_at,
        )
        emitted.extend(horizon_events)

        ghost_statuses = _final_statuses(ghost_runtime)

        # Real timeline: replay the full persisted history on a second throwaway runtime.
        real_runtime = self._build_runtime(run_id, seed, scenario_version_id)
        self._rcs._replay_events(real_runtime, sim_events)  # noqa: SLF001
        real_statuses = _final_statuses(real_runtime)

        real_outcome = _build_outcome("real", real_statuses)
        ghost_outcome = _build_outcome("ghost", ghost_statuses)
        diffs = _asset_diffs(real_statuses, ghost_statuses)
        timeline = _ghost_timeline(emitted, plan.fork_sequence)
        verdict = _build_verdict(decision, request, diffs, real_outcome, ghost_outcome)

        return GhostBranchResultV1(
            schema_version=GHOST_BRANCH_RESULT_SCHEMA_VERSION,
            run_id=run_id,
            decision_ref=request.decision_ref,
            mode=request.mode,
            request_fingerprint=_request_fingerprint(run_id, request),
            result_hash=_result_hash(ghost_statuses, timeline),
            divergence_sequence=plan.fork_sequence,
            divergence_sim_time=_iso(plan.divergence_sim_time),
            steps_simulated=steps,
            real_outcome=real_outcome,
            ghost_outcome=ghost_outcome,
            asset_diffs=diffs,
            ghost_timeline=timeline,
            real_overall_score=real_overall_score,
            verdict=verdict,
        )

    # -- helpers --------------------------------------------------------------------

    async def _load_sim_events(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> list[DomainEventEnvelopeV1]:
        events = await PostgresEventQueryRepository(uow.session).list_by_run(
            run_id, limit=100_000
        )
        return [event for event in events if _is_sim_event(event)]

    def _build_runtime(
        self, run_id: str, seed: int, scenario_version_id: str
    ) -> SimulationRuntime:
        package_dir = self._rcs.resolve_package_dir(
            package_path=None, scenario_version_id=scenario_version_id
        )
        manifest = SimulationEngine.load_manifest(package_dir)
        # Reuse the real run id: the runtime is a throwaway that emits events only into its
        # in-memory ``events`` list (never persisted), and event envelopes validate the
        # ``run_<ULID>`` id format. Determinism is driven by seed + manifest, which match
        # the real run exactly.
        return SimulationEngine.create_runtime(
            manifest=manifest,
            seed=seed,
            scenario_version_id=scenario_version_id,
            run_id=run_id,
        )


def _enumerate_decision_points(
    sim_events: list[DomainEventEnvelopeV1],
) -> list[GhostDecisionPointV1]:
    points: list[GhostDecisionPointV1] = []
    index = 0
    total = len(sim_events)
    # Executed operator/agent actions: contiguous same-sim_time blocks terminated by a
    # ``sim.command.executed`` — the unique signature of a runtime EXECUTE (scheduled
    # attacker effects never emit that terminator).
    while index < total:
        block_end = RunCommandService._execute_block_end(sim_events, index)  # noqa: SLF001
        if block_end is None:
            index += 1
            continue
        block = sim_events[index:block_end]
        first = block[0]
        effect = next((e for e in block if e.type == "sim.asset.status_changed"), None)
        if effect is not None:
            asset_id = str(effect.payload.get("assetId", "")) or None
            status = str(effect.payload.get("status", ""))
            command = STATUS_TO_COMMAND.get(status)
            action_class = (
                COMMAND_TO_ACTION_CLASS[command].value if command is not None else None
            )
            points.append(
                GhostDecisionPointV1(
                    schema_version=GHOST_DECISION_POINT_SCHEMA_VERSION,
                    decision_ref=f"execact:{first.sequence}",
                    kind=GhostDecisionKindV1.EXECUTED_ACTION,
                    sequence=first.sequence,
                    sim_time=_iso(first.sim_time),
                    scenario_command=command,
                    target_asset_id=asset_id,
                    action_class=action_class,
                    label=_executed_label(command, status, asset_id, first.sim_time),
                )
            )
        index = block_end

    # Salient inaction windows: the first attacker foothold and the first adversary asset
    # impact — points where doing something (vs the operator's real inaction) is meaningful.
    triggered = next(
        (e for e in sim_events if e.type == "sim.hidden_condition.triggered"), None
    )
    if triggered is not None:
        points.append(
            GhostDecisionPointV1(
                schema_version=GHOST_DECISION_POINT_SCHEMA_VERSION,
                decision_ref=f"inaction:{triggered.sequence}",
                kind=GhostDecisionKindV1.INACTION_WINDOW,
                sequence=triggered.sequence,
                sim_time=_iso(triggered.sim_time),
                scenario_command=None,
                target_asset_id=None,
                action_class=None,
                label=f"Inaction window — first attacker foothold @ {_iso(triggered.sim_time)}",
            )
        )
    impact = next(
        (
            e
            for e in sim_events
            if e.type == "sim.asset.status_changed"
            and str(e.payload.get("status", "")) in _ADVERSARY_STATUSES
        ),
        None,
    )
    if impact is not None:
        impact_asset = str(impact.payload.get("assetId", "")) or None
        points.append(
            GhostDecisionPointV1(
                schema_version=GHOST_DECISION_POINT_SCHEMA_VERSION,
                decision_ref=f"inaction:{impact.sequence}",
                kind=GhostDecisionKindV1.INACTION_WINDOW,
                sequence=impact.sequence,
                sim_time=_iso(impact.sim_time),
                scenario_command=None,
                target_asset_id=impact_asset,
                action_class=None,
                label=f"Inaction window — {impact_asset or 'asset'} first shows adversary activity",
            )
        )

    # Stable ordering; dedupe by decision_ref (an impact could coincide with a block start).
    seen: set[str] = set()
    unique: list[GhostDecisionPointV1] = []
    for point in sorted(points, key=lambda p: (p.sequence, p.decision_ref)):
        if point.decision_ref in seen:
            continue
        seen.add(point.decision_ref)
        unique.append(point)
    return unique


def _plan_fork(
    decision: GhostDecisionPointV1,
    request: GhostBranchRequestV1,
    sim_events: list[DomainEventEnvelopeV1],
) -> _DecisionPlan:
    decision_time = _parse_sim_time(decision.sim_time, sim_events, decision.sequence)

    if request.mode == GhostBranchModeV1.DO_NOTHING:
        return _DecisionPlan(
            fork_sequence=decision.sequence,
            divergence_sim_time=decision_time,
            command=None,
            target_asset_id=None,
            apply_at=None,
        )

    if request.mode == GhostBranchModeV1.SUBSTITUTE:
        command = request.alternate_command
        target = request.alternate_target_asset_id or decision.target_asset_id
        if target is None:
            raise GhostBranchError(
                code="TARGET_REQUIRED",
                message="substitute at an inaction window requires alternateTargetAssetId",
            )
        return _DecisionPlan(
            fork_sequence=decision.sequence,
            divergence_sim_time=decision_time,
            command=command,
            target_asset_id=target,
            apply_at=None,
        )

    # SHIFT: keep the real command, apply it earlier or later.
    if decision.scenario_command is None:
        raise GhostBranchError(
            code="SHIFT_UNSUPPORTED",
            message="shift requires an executed-action decision (nothing to move)",
        )
    shift = int(request.shift_sim_seconds or 0)
    target_time = decision_time + timedelta(seconds=shift)
    if shift < 0:
        # Fork earlier: replay everything at sim_time <= target, then apply immediately.
        fork_sequence = _first_sequence_after(sim_events, target_time)
        return _DecisionPlan(
            fork_sequence=fork_sequence,
            divergence_sim_time=target_time,
            command=decision.scenario_command,
            target_asset_id=decision.target_asset_id,
            apply_at=None,
        )
    # Fork at the decision (dropping the real action), inject once the clock reaches target.
    return _DecisionPlan(
        fork_sequence=decision.sequence,
        divergence_sim_time=target_time,
        command=decision.scenario_command,
        target_asset_id=decision.target_asset_id,
        apply_at=target_time,
    )


def _parse_sim_time(
    sim_time: str, sim_events: list[DomainEventEnvelopeV1], sequence: int
) -> datetime:
    for event in sim_events:
        if event.sequence == sequence:
            return event.sim_time
    return datetime.fromisoformat(sim_time.replace("Z", "+00:00"))


def _first_sequence_after(
    sim_events: list[DomainEventEnvelopeV1], target_time: datetime
) -> int:
    for event in sim_events:
        if event.sim_time > target_time:
            return event.sequence
    # Nothing later than the target — fork at the very end (degenerate, but bounded).
    return sim_events[-1].sequence + 1 if sim_events else 1


def _ensure_running(runtime: SimulationRuntime) -> None:
    status = runtime.world.status
    if status == SimulationRunStatus.CREATED:
        runtime.start()
    elif status == SimulationRunStatus.PAUSED:
        runtime.resume()
    elif status == SimulationRunStatus.STOPPED:
        # A run stopped before the fork cannot advance; the counterfactual reopens it.
        runtime.world.status = SimulationRunStatus.RUNNING


def _apply_command(
    runtime: SimulationRuntime, command: Any, target_asset_id: str | None
) -> list[DomainEventEnvelopeV1]:
    if target_asset_id is None:
        return []
    status = COMMAND_STATUS_MAP[command]
    sim_command = SimulationCommandV1(
        schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
        command_id=f"ghost-{command.value}-{target_asset_id}-{runtime.world.next_sequence}",
        command_type=SimulationCommandType.EXECUTE,
        run_id=runtime.run_id,
        actor=ActorRef(type=ActorType.OPERATOR, id="asset:ghost-operator"),
        authorization_token="ghost-branch",
        payload={
            "pluginId": "effect.set_asset_status",
            "targetAssetId": target_asset_id,
            "config": {"assetId": target_asset_id, "status": status},
        },
    )
    try:
        return runtime.execute_command(sim_command)
    except SimulationError as exc:  # pragma: no cover - defensive
        raise GhostBranchError(
            code="GHOST_EXECUTE_FAILED", message=exc.message, status_code=500
        ) from exc


def _step_to_horizon(
    runtime: SimulationRuntime,
    *,
    pending_command: Any | None,
    target_asset_id: str | None,
    apply_at: datetime | None,
) -> tuple[list[DomainEventEnvelopeV1], int]:
    emitted: list[DomainEventEnvelopeV1] = []
    applied = pending_command is None or apply_at is None
    steps = 0
    while steps < GHOST_MAX_STEPS:
        if runtime.world.status != SimulationRunStatus.RUNNING:
            break
        peek = runtime.queue.peek()
        if peek is None:
            break
        if not applied and apply_at is not None and peek.sim_time >= apply_at:
            emitted.extend(_apply_command(runtime, pending_command, target_asset_id))
            applied = True
        batch = runtime.step()
        steps += 1
        emitted.extend(batch)
    if not applied and pending_command is not None:
        # Target time lay beyond the horizon; apply at the end so the action still happens.
        emitted.extend(_apply_command(runtime, pending_command, target_asset_id))
    return emitted, steps


def _final_statuses(runtime: SimulationRuntime) -> dict[str, str]:
    return {asset_id: asset.status for asset_id, asset in runtime.world.assets.items()}


def _build_outcome(label: str, statuses: dict[str, str]) -> GhostOutcomeV1:
    compromised = sorted(a for a, s in statuses.items() if s in _ADVERSARY_STATUSES)
    contained = [a for a, s in statuses.items() if s in _CONTAINED_STATUSES]
    breach = sorted(a for a, s in statuses.items() if s in _BREACH_STATUSES)
    return GhostOutcomeV1(
        label=label,
        final_statuses=[
            GhostAssetStatusV1(asset_id=asset_id, status=status)
            for asset_id, status in sorted(statuses.items())
        ],
        compromised_count=len(compromised),
        contained_count=len(contained),
        breach_occurred=bool(breach),
        breach_asset_ids=breach,
    )


def _asset_diffs(
    real: dict[str, str], ghost: dict[str, str]
) -> list[GhostAssetDiffV1]:
    diffs: list[GhostAssetDiffV1] = []
    for asset_id in sorted(set(real) | set(ghost)):
        real_status = real.get(asset_id, "absent")
        ghost_status = ghost.get(asset_id, "absent")
        if real_status != ghost_status:
            diffs.append(
                GhostAssetDiffV1(
                    asset_id=asset_id,
                    real_status=real_status,
                    ghost_status=ghost_status,
                )
            )
    return diffs


def _ghost_timeline(
    emitted: list[DomainEventEnvelopeV1], fork_sequence: int
) -> list[GhostTimelineBeatV1]:
    beats: list[GhostTimelineBeatV1] = []
    for event in emitted:
        if event.sequence < fork_sequence:
            continue
        kind = _TIMELINE_KINDS.get(event.type)
        if event.type == "sim.asset.status_changed":
            status = str(event.payload.get("status", ""))
            if status not in _ADVERSARY_STATUSES:
                continue  # keep the attacker lane to adversary impact only
            asset_id = str(event.payload.get("assetId", "")) or None
            beats.append(
                GhostTimelineBeatV1(
                    sequence=event.sequence,
                    sim_time=_iso(event.sim_time),
                    kind="asset_status",
                    label=f"{asset_id or 'asset'} → {status}",
                    asset_id=asset_id,
                    status=status,
                )
            )
            continue
        if kind is None:
            continue
        condition_id = str(event.payload.get("conditionId", "")) or None
        branch_id = str(event.payload.get("branchId", "")) or None
        label = condition_id or branch_id or event.type
        beats.append(
            GhostTimelineBeatV1(
                sequence=event.sequence,
                sim_time=_iso(event.sim_time),
                kind=kind,
                label=label,
                asset_id=None,
                status=None,
            )
        )
    return beats


def _build_verdict(
    decision: GhostDecisionPointV1,
    request: GhostBranchRequestV1,
    diffs: list[GhostAssetDiffV1],
    real: GhostOutcomeV1,
    ghost: GhostOutcomeV1,
) -> str:
    if not diffs:
        return "No divergence: the alternate decision produced an identical final outcome."
    breach_prevented = set(real.breach_asset_ids) - set(ghost.breach_asset_ids)
    new_breach = set(ghost.breach_asset_ids) - set(real.breach_asset_ids)
    parts: list[str] = []
    if breach_prevented:
        parts.append(f"prevents the breach on {', '.join(sorted(breach_prevented))}")
    if new_breach:
        parts.append(f"leaves {', '.join(sorted(new_breach))} breached")
    service_delta = ghost.contained_count - real.contained_count
    if service_delta > 0:
        parts.append(f"service impact +{service_delta} asset(s) contained")
    elif service_delta < 0:
        parts.append(f"service impact {service_delta} asset(s) contained")
    if not parts:
        parts.append(f"changes the final status of {len(diffs)} asset(s)")
    lead = _verdict_lead(decision, request)
    return f"{lead} {'; '.join(parts)}."


def _verdict_lead(decision: GhostDecisionPointV1, request: GhostBranchRequestV1) -> str:
    if request.mode == GhostBranchModeV1.DO_NOTHING:
        return "Doing nothing here"
    if request.mode == GhostBranchModeV1.SHIFT:
        shift = int(request.shift_sim_seconds or 0)
        minutes = abs(shift) // 60
        seconds = abs(shift) % 60
        when = f"{minutes}m" if seconds == 0 else f"{minutes}m{seconds}s"
        direction = "earlier" if shift < 0 else "later"
        cmd = decision.scenario_command.value if decision.scenario_command else "the action"
        return f"Applying {cmd} on {decision.target_asset_id} {when} {direction}"
    command = request.alternate_command.value if request.alternate_command else "the action"
    target = request.alternate_target_asset_id or decision.target_asset_id
    return f"Choosing {command} on {target} instead"


def _executed_label(
    command: Any | None, status: str, asset_id: str | None, sim_time: datetime
) -> str:
    name = command.value if command is not None else status
    return f"{name} on {asset_id or 'asset'} @ {_iso(sim_time)}"


def _request_fingerprint(run_id: str, request: GhostBranchRequestV1) -> str:
    raw = "|".join(
        [
            run_id,
            request.decision_ref,
            request.mode.value,
            request.alternate_command.value if request.alternate_command else "-",
            request.alternate_target_asset_id or "-",
            str(request.shift_sim_seconds if request.shift_sim_seconds is not None else "-"),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _result_hash(
    statuses: dict[str, str], timeline: list[GhostTimelineBeatV1]
) -> str:
    canonical = ";".join(f"{a}:{s}" for a, s in sorted(statuses.items()))
    canonical += "||" + ";".join(
        f"{b.sequence}:{b.kind}:{b.asset_id or ''}:{b.status or ''}" for b in timeline
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
