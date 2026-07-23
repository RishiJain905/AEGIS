"""Unit tests for auto after-action finalization when a run stops.

Offline: the unit of work and the scoring / report collaborators are faked so the
best-effort contract (score attempted, failures swallowed) is verified without a DB.
"""

from __future__ import annotations

from types import SimpleNamespace

import aegis_api.runs.lifecycle as lifecycle
import pytest


class _FakeUow:
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
