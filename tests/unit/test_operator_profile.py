"""Unit tests for the operator skill-telemetry profile assembler.

Uses a lightweight in-memory fake unit of work so the metric-derivation and coaching logic is
tested deterministically without a database.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from aegis_scoring.operator_profile import assemble_operator_profile


def _event(seq: int, etype: str, *, asset: str | None = None, **payload: Any) -> SimpleNamespace:
    body = dict(payload)
    if asset is not None:
        body.setdefault("assetId", asset)
    return SimpleNamespace(
        event_id=f"evt-{seq}",
        sequence=seq,
        type=etype,
        payload=body,
        subject=SimpleNamespace(id=asset or "system"),
        sim_time=None,
    )


def _proposal(
    pid: str, action_class: str, target: str, status: str = "executed"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=pid,
        action_class=action_class,
        target_asset_id=target,
        status=status,
    )


class _FakeInvestigation:
    def __init__(self, details: dict[str, SimpleNamespace]) -> None:
        self._details = details

    async def get_detail(self, incident_id: str, run_id: str) -> SimpleNamespace:  # noqa: ARG002
        return self._details[incident_id]


class _FakeRepo:
    def __init__(self, by_run: dict[str, list[Any]]) -> None:
        self._by_run = by_run

    async def list_by_run(self, run_id: str, limit: int | None = None) -> list[Any]:  # noqa: ARG002
        return list(self._by_run.get(run_id, []))


class _FakeRunScores:
    def __init__(self, scores: dict[str, SimpleNamespace]) -> None:
        self._scores = scores

    async def get_latest_for_run(self, run_id: str) -> SimpleNamespace | None:
        return self._scores.get(run_id)


class _FakeRuns:
    def __init__(self, runs: list[SimpleNamespace]) -> None:
        self._runs = runs

    async def list_for_owner(self, owner_user_id: str) -> list[SimpleNamespace]:  # noqa: ARG002
        # Newest-first, mirroring the real repository ordering.
        return list(self._runs)


class _FakeUow:
    def __init__(
        self,
        *,
        runs: list[SimpleNamespace],
        events: dict[str, list[Any]],
        incidents: dict[str, list[Any]],
        details: dict[str, SimpleNamespace],
        scores: dict[str, SimpleNamespace],
    ) -> None:
        self.runs = _FakeRuns(runs)
        self.events = _FakeRepo(events)
        self.incidents = _FakeRepo(incidents)
        self.investigation = _FakeInvestigation(details)
        self.run_scores = _FakeRunScores(scores)


def _run(run_id: str, status: str = "stopped") -> SimpleNamespace:
    return SimpleNamespace(
        id=run_id,
        seed=42,
        status=status,
        started_at="2026-01-01T00:00:00Z",
        scenario_version_id="scenario-version:1.0.0",
    )


@pytest.mark.asyncio
async def test_assembles_metrics_from_synthetic_runs() -> None:
    # Run A: alert@5, TRACE session, task@8 (triage=3); hidden-condition reveals the true
    # attack path on asset:records; an aggressive action hits an OFF-path asset (over-contain)
    # and executes at seq 12 (containment latency = 7).
    events_a = [
        _event(2, "agent.session.started", sessionId="s1", role="TRACE"),
        _event(5, "alert.created", asset="asset:records"),
        _event(8, "agent.task.started", sessionId="s1"),
        _event(9, "sim.hidden_condition.revealed", asset="asset:records"),
        _event(12, "action.executed", proposalId="p1"),
    ]
    details_a = SimpleNamespace(
        proposals=[_proposal("p1", "class_2", "asset:printer")],  # off-path target
        executed_actions=[SimpleNamespace(proposal_id="p1", id="act1")],
        hypotheses=[SimpleNamespace(status="refuted"), SimpleNamespace(status="confirmed")],
    )

    # Run B: no hidden-condition surfaces (attack path unknown → over-containment not judged).
    events_b = [
        _event(3, "alert.created", asset="asset:db"),
        _event(6, "agent.task.started", sessionId="s2"),
    ]
    details_b = SimpleNamespace(proposals=[], executed_actions=[], hypotheses=[])

    uow = _FakeUow(
        runs=[_run("run_b"), _run("run_a")],  # newest-first
        events={"run_a": events_a, "run_b": events_b},
        incidents={"run_a": [SimpleNamespace(id="inc_a")], "run_b": [SimpleNamespace(id="inc_b")]},
        details={"inc_a": details_a, "inc_b": details_b},
        scores={
            "run_a": SimpleNamespace(overall_score=6.0, max_score=10.0),
            "run_b": SimpleNamespace(overall_score=8.0, max_score=10.0),
        },
    )

    profile = await assemble_operator_profile(uow, owner_user_id="user:op")

    assert profile.metrics.runs_analyzed == 2
    # Oldest→newest ordering: run_a then run_b.
    assert [s.run_id for s in profile.runs] == ["run_a", "run_b"]

    run_a = profile.runs[0]
    assert run_a.time_to_first_triage == 3.0
    assert run_a.first_agent_role == "TRACE"
    assert run_a.containment_latency == 7.0
    assert run_a.aggressive_action_count == 1
    assert run_a.over_containment_count == 1  # off-path target, attack path known
    assert run_a.hypothesis_count == 2
    assert run_a.false_hypothesis_count == 1

    run_b = profile.runs[1]
    assert run_b.over_containment_count is None  # attack path unknown → not judged

    # Aggregate: over-containment ratio computed only over judged runs (run_a): 1/1.
    assert profile.metrics.over_containment_ratio == pytest.approx(1.0)
    assert profile.metrics.false_hypothesis_rate == pytest.approx(0.5)
    assert profile.metrics.score_trend == [pytest.approx(0.6), pytest.approx(0.8)]
    assert profile.metrics.avg_score == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_excludes_non_terminal_runs_and_handles_empty() -> None:
    uow = _FakeUow(
        runs=[_run("run_live", status="running")],
        events={},
        incidents={},
        details={},
        scores={},
    )
    profile = await assemble_operator_profile(uow, owner_user_id="user:op")
    assert profile.metrics.runs_analyzed == 0
    assert profile.runs == []
    # Thin-data coaching line is emitted honestly.
    assert any(line.id == "thin-data" for line in profile.coaching)


@pytest.mark.asyncio
async def test_over_containment_coaching_fires_when_ratio_high() -> None:
    # Two judged terminal runs, each with an off-path aggressive action → ratio 1.0 >= 0.4.
    def make_run(rid: str) -> tuple[SimpleNamespace, list[Any], SimpleNamespace]:
        events = [
            _event(1, "alert.created", asset="asset:records"),
            _event(2, "sim.hidden_condition.triggered", asset="asset:records"),
            _event(5, "action.executed", proposalId=f"{rid}-p"),
        ]
        detail = SimpleNamespace(
            proposals=[_proposal(f"{rid}-p", "class_3", "asset:printer")],
            executed_actions=[SimpleNamespace(proposal_id=f"{rid}-p", id=f"{rid}-a")],
            hypotheses=[],
        )
        return _run(rid), events, detail

    r1, e1, d1 = make_run("run_1")
    r2, e2, d2 = make_run("run_2")
    r3, e3, d3 = make_run("run_3")
    uow = _FakeUow(
        runs=[r3, r2, r1],
        events={"run_1": e1, "run_2": e2, "run_3": e3},
        incidents={rid: [SimpleNamespace(id=f"inc-{rid}")] for rid in ("run_1", "run_2", "run_3")},
        details={"inc-run_1": d1, "inc-run_2": d2, "inc-run_3": d3},
        scores={},
    )
    profile = await assemble_operator_profile(uow, owner_user_id="user:op")
    assert profile.metrics.over_containment_ratio == pytest.approx(1.0)
    assert any(
        line.id == "over-containment" and line.tone == "improve" for line in profile.coaching
    )
