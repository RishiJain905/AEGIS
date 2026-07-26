"""Offline tests for the ``restartExisting`` reset-and-replay relaunch path.

A pinned-seed scenario derives exactly one run id from (seed, scenarioVersionId), so the
guided tutorial resolves to the same run id forever: the first launch creates it and every
later launch used to resume that (by then finished) run. ``restartExisting`` destroys the
run instead and rebuilds it under the same id. These tests pin the decision logic — who may
reset, and what a reset tears down — without PostgreSQL; the cascade itself is covered by
``tests/integration/run-api/test_run_restart.py``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aegis_contracts import RunCreateRequestV1, RunV1
from aegis_contracts.versioning import RUN_CREATE_REQUEST_SCHEMA_VERSION, RUN_SCHEMA_VERSION
from aegis_simulation.application import SIMULATION_COMMAND_SCOPE
from aegis_simulation.run_command_service import (
    RunCommandService,
    RuntimeCacheEntry,
    may_reset_run,
)
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.ids import derive_run_id

FIXTURE_PACKAGE = "scenarios/_fixtures/valid-minimal"
SEED = 1000
OWNER = "user:operator-alpha"
OTHER = "user:operator-bravo"


class _ReachedCreation(Exception):
    """Raised by the fake scenario repository once ``create_run`` starts building a run."""


@dataclass
class _FakeRunRepository:
    run: RunV1 | None
    deleted: list[str] = field(default_factory=list)

    async def get_by_id(self, run_id: str) -> RunV1 | None:
        return self.run if self.run is not None and self.run.id == run_id else None

    async def delete(self, run_id: str) -> bool:
        self.deleted.append(run_id)
        existed = self.run is not None
        self.run = None
        return existed


@dataclass
class _FakeIdempotencyRepository:
    purged: list[tuple[str, str]] = field(default_factory=list)

    async def get(self, *, scope: str, idempotency_key: str) -> None:
        _ = (scope, idempotency_key)
        return None

    async def delete_by_response_ref(self, *, scope: str, response_ref: str) -> int:
        self.purged.append((scope, response_ref))
        return 1


class _FakeScenarioRepository:
    async def get_by_id(self, scenario_id: str) -> None:
        raise _ReachedCreation(scenario_id)


@dataclass
class _FakeUnitOfWork:
    """The slice of the unit of work ``create_run`` touches before it builds a run."""

    runs: _FakeRunRepository
    idempotency: _FakeIdempotencyRepository = field(default_factory=_FakeIdempotencyRepository)
    scenarios: _FakeScenarioRepository = field(default_factory=_FakeScenarioRepository)


def _scenario_version_id() -> str:
    manifest = SimulationEngine.load_manifest(Path(FIXTURE_PACKAGE))
    return f"scenario-version:{manifest.metadata.version}"


def _derived_run_id() -> str:
    return derive_run_id(run_seed=SEED, scenario_version_id=_scenario_version_id())


def _existing_run(*, owner_user_id: str | None, status: str = "stopped") -> RunV1:
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=_derived_run_id(),
        scenario_version_id=_scenario_version_id(),
        seed=SEED,
        status=status,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, tzinfo=UTC),
        revision=7,
        owner_user_id=owner_user_id,
    )


def _request(*, restart_existing: bool) -> RunCreateRequestV1:
    return RunCreateRequestV1(
        schemaVersion=RUN_CREATE_REQUEST_SCHEMA_VERSION,
        scenarioPackagePath=FIXTURE_PACKAGE,
        seed=SEED,
        restartExisting=restart_existing,
    )


def _create(
    service: RunCommandService,
    uow: _FakeUnitOfWork,
    *,
    restart_existing: bool,
    owner_user_id: str | None = OWNER,
    requester_is_admin: bool = False,
) -> Any:
    return asyncio.run(
        service.create_run(
            uow,  # type: ignore[arg-type]
            _request(restart_existing=restart_existing),
            idempotency_key="launch-key-1",
            owner_user_id=owner_user_id,
            requester_is_admin=requester_is_admin,
        )
    )


# --- who may reset ----------------------------------------------------------------


def test_owner_may_reset_their_own_run() -> None:
    run = _existing_run(owner_user_id=OWNER)
    assert may_reset_run(run, requester_user_id=OWNER, requester_is_admin=False)


def test_non_owner_may_not_reset_another_operators_run() -> None:
    run = _existing_run(owner_user_id=OWNER)
    assert not may_reset_run(run, requester_user_id=OTHER, requester_is_admin=False)


def test_admin_may_reset_any_run() -> None:
    run = _existing_run(owner_user_id=OWNER)
    assert may_reset_run(run, requester_user_id=OTHER, requester_is_admin=True)


def test_unowned_run_is_admin_only() -> None:
    """Legacy/seeded demo runs have no owner and must not be destroyable by an operator."""
    run = _existing_run(owner_user_id=None)
    assert not may_reset_run(run, requester_user_id=OWNER, requester_is_admin=False)
    assert may_reset_run(run, requester_user_id=OWNER, requester_is_admin=True)


# --- create_run behaviour ---------------------------------------------------------


def test_absent_flag_returns_the_existing_run_untouched() -> None:
    """Today's behaviour is the default: no flag, no reset, resume the deterministic run."""
    existing = _existing_run(owner_user_id=OWNER)
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    response = _create(service, uow, restart_existing=False)

    assert response.run.id == existing.id
    assert response.run.revision == existing.revision
    assert response.events_emitted == 0
    assert response.idempotency is not None
    assert response.idempotency.replayed is True
    assert uow.runs.deleted == []
    assert uow.idempotency.purged == []


def test_restart_by_a_non_owner_falls_back_to_returning_the_existing_run() -> None:
    """An unauthorized restart degrades to a resume rather than erroring or resetting."""
    existing = _existing_run(owner_user_id=OWNER)
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    response = _create(service, uow, restart_existing=True, owner_user_id=OTHER)

    assert response.run.id == existing.id
    assert uow.runs.deleted == []


def test_restart_by_the_owner_deletes_the_run_then_creates_a_new_one() -> None:
    """The authorized path tears the run down and falls through to the creation path.

    The fake scenario repository marks the point where ``create_run`` starts building the
    replacement run, which is the observable that matters here: the delete happened *and*
    creation proceeded rather than the call short-circuiting into a resume.
    """
    existing = _existing_run(owner_user_id=OWNER)
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    with pytest.raises(_ReachedCreation):
        _create(service, uow, restart_existing=True)

    assert uow.runs.deleted == [existing.id]
    # The destroyed run's simulation-command records go too: the START fallback command id
    # is derived from (seed, run_id) and would otherwise read as a duplicate, leaving the
    # recreated run persisted but never started.
    assert uow.idempotency.purged == [(SIMULATION_COMMAND_SCOPE, existing.id)]


def test_restart_by_an_admin_deletes_another_operators_run() -> None:
    existing = _existing_run(owner_user_id=OWNER)
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    with pytest.raises(_ReachedCreation):
        _create(
            service,
            uow,
            restart_existing=True,
            owner_user_id=OTHER,
            requester_is_admin=True,
        )

    assert uow.runs.deleted == [existing.id]


# --- what a reset tears down ------------------------------------------------------


def test_reset_drops_every_piece_of_in_process_state_keyed_by_the_run_id() -> None:
    """The fresh run reuses the id, so cached runtime, tempo and observers must be cleared."""
    existing = _existing_run(owner_user_id=OWNER)
    run_id = existing.id
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    runtime = SimulationEngine.create_runtime(
        manifest=SimulationEngine.load_manifest(Path(FIXTURE_PACKAGE)),
        seed=SEED,
        scenario_version_id=_scenario_version_id(),
        run_id=run_id,
    )
    service.runtime_cache[run_id] = RuntimeCacheEntry(
        runtime=runtime, package_dir=Path(FIXTURE_PACKAGE)
    )
    service.set_threat_tempo(run_id, 0.75)
    notified: list[str] = []
    service.add_run_reset_listener(notified.append)

    asyncio.run(service._reset_run(uow, run_id))  # type: ignore[arg-type]

    assert run_id not in service.runtime_cache
    assert service.get_threat_tempo(run_id) is None
    assert notified == [run_id]
    assert uow.runs.deleted == [run_id]


def test_reset_listeners_can_be_deregistered() -> None:
    service = RunCommandService(workspace_root=Path("."))
    notified: list[str] = []

    service.add_run_reset_listener(notified.append)
    service.add_run_reset_listener(notified.append)  # idempotent registration
    service.remove_run_reset_listener(notified.append)
    service.remove_run_reset_listener(notified.append)  # tolerates an absent listener

    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=None))
    asyncio.run(service._reset_run(uow, "run_absent"))  # type: ignore[arg-type]

    assert notified == []
