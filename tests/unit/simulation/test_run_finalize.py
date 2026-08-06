"""Unit tests for auto after-action finalization when a run stops.

Offline: the unit of work and the scoring / report collaborators are faked so the
best-effort contract (score attempted, failures swallowed) is verified without a DB.
"""

from __future__ import annotations

from types import SimpleNamespace

import aegis_api.runs.lifecycle as lifecycle
import pytest


class _FakeAgentTasks:
    async def get_by_id(self, task_id: str) -> object:
        return SimpleNamespace(id=task_id, status=SimpleNamespace(value="queued"))

    async def list_for_run(
        self, run_id: str, *, statuses: tuple[str, ...] | None = None
    ) -> list[object]:
        return []


class _FakeUow:
    def __init__(self) -> None:
        self.agent_tasks = _FakeAgentTasks()

    async def __aenter__(self) -> _FakeUow:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def _fake_uow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "PostgresUnitOfWork", lambda *a, **k: _FakeUow())


@pytest.mark.asyncio
async def test_finalize_scores_the_stopped_run(monkeypatch: pytest.MonkeyPatch) -> None:
    scored: list[str] = []

    async def _score(uow: object, *, run_id: str, scenarios_root: object) -> object:
        scored.append(run_id)
        return SimpleNamespace()

    async def _no_report(session_maker: object, *, run_id: str, settings: object) -> None:
        return None

    monkeypatch.setattr(lifecycle._scoring_service, "score_run", _score)
    monkeypatch.setattr(lifecycle, "_generate_after_action_report", _no_report)

    await lifecycle.finalize_stopped_run(lambda: None, run_id="run:1", settings=None)  # type: ignore[arg-type]

    assert scored == ["run:1"]


@pytest.mark.asyncio
async def test_finalize_swallows_scoring_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(uow: object, *, run_id: str, scenarios_root: object) -> object:
        raise RuntimeError("scoring exploded")

    async def _no_report(session_maker: object, *, run_id: str, settings: object) -> None:
        return None

    monkeypatch.setattr(lifecycle._scoring_service, "score_run", _boom)
    monkeypatch.setattr(lifecycle, "_generate_after_action_report", _no_report)

    # Must not raise: finalization runs after the STOP commits and must never fail it.
    await lifecycle.finalize_stopped_run(lambda: None, run_id="run:1", settings=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_finalize_swallows_missing_investigation_for_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scored: list[str] = []

    async def _score(uow: object, *, run_id: str, scenarios_root: object) -> object:
        scored.append(run_id)
        return SimpleNamespace()

    async def _report_boom(session_maker: object, *, run_id: str, settings: object) -> None:
        raise RuntimeError("no incident / missing artifacts")

    monkeypatch.setattr(lifecycle._scoring_service, "score_run", _score)
    monkeypatch.setattr(lifecycle, "_generate_after_action_report", _report_boom)

    # A run with no complete investigation still scores; the report is simply skipped.
    await lifecycle.finalize_stopped_run(lambda: None, run_id="run:1", settings=None)  # type: ignore[arg-type]
    assert scored == ["run:1"]


@pytest.mark.asyncio
async def test_report_generation_degrades_without_agent_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The common case now succeeds instead of being skipped.

    A stopped run whose agents produced nothing takes the deterministic branch and never
    builds the task executor, so finalization does not depend on a reachable provider.
    """
    from aegis_agents.roles.scribe.coordinator import (
        ScribeCoordinator,
        ScribeEnsureResult,
        ScribeReportOutcome,
    )

    calls: list[str] = []

    async def _ensure(self: object, uow: object, request: object) -> ScribeEnsureResult:
        calls.append("ensure")
        return ScribeEnsureResult(
            outcome=ScribeReportOutcome.DETERMINISTIC,
            incident_id="incident:inc_001",
            report_version_id="rpv_stub",
        )

    def _no_executor() -> object:
        raise AssertionError("deterministic finalization must not build the task executor")

    monkeypatch.setattr(ScribeCoordinator, "ensure_report_for_run", _ensure)
    monkeypatch.setattr(lifecycle, "create_task_executor", _no_executor)

    await lifecycle._generate_after_action_report(
        lambda: None,  # type: ignore[arg-type]
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        settings=None,
    )

    assert calls == ["ensure"]


@pytest.mark.asyncio
async def test_failed_agent_task_falls_back_to_a_deterministic_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A complete investigation whose SCRIBE run explodes still lands a report."""
    from aegis_agents.roles.scribe.coordinator import (
        ScribeCoordinator,
        ScribeEnsureResult,
        ScribeReportOutcome,
    )

    calls: list[str] = []

    async def _ensure(self: object, uow: object, request: object) -> ScribeEnsureResult:
        calls.append("agent")
        return ScribeEnsureResult(
            outcome=ScribeReportOutcome.AGENT_TASK_QUEUED,
            incident_id="incident:inc_001",
            scribe_session_id="agent-session:ags_stub",
            scribe_task_id="tsk_stub",
        )

    async def _ensure_deterministic(
        self: object,
        uow: object,
        request: object,
        *,
        incident_id: str | None = None,
    ) -> ScribeEnsureResult:
        calls.append("deterministic")
        return ScribeEnsureResult(
            outcome=ScribeReportOutcome.DETERMINISTIC,
            incident_id="incident:inc_001",
            report_version_id="rpv_stub",
        )

    class _ExplodingExecutor:
        async def execute(self, uow: object, *, task_id: str) -> None:
            raise RuntimeError("provider unreachable")

    monkeypatch.setattr(ScribeCoordinator, "ensure_report_for_run", _ensure)
    monkeypatch.setattr(ScribeCoordinator, "ensure_deterministic_report", _ensure_deterministic)
    monkeypatch.setattr(lifecycle, "create_task_executor", _ExplodingExecutor)

    await lifecycle._generate_after_action_report(
        lambda: None,  # type: ignore[arg-type]
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        settings=None,
    )

    assert calls == ["agent", "deterministic"]
