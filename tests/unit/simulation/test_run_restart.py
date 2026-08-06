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
    scoped_create_idempotency_key,
)
from aegis_simulation_domain import SimulationEngine, SimulationError, SimulationErrorCode
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
class _FakeIdempotencyRecord:
    response_ref: str


@dataclass
class _FakeIdempotencyRepository:
    purged: list[tuple[str, str]] = field(default_factory=list)
    # Stored key -> run id, so a test can assert which key the lookup actually used.
    records: dict[str, str] = field(default_factory=dict)
    looked_up: list[str] = field(default_factory=list)

    async def get(self, *, scope: str, idempotency_key: str) -> _FakeIdempotencyRecord | None:
        _ = scope
        self.looked_up.append(idempotency_key)
        run_id = self.records.get(idempotency_key)
        return _FakeIdempotencyRecord(response_ref=run_id) if run_id is not None else None

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


def test_launch_by_a_non_owner_is_refused_instead_of_handing_over_a_foreign_run() -> None:
    """A launch must never resolve to a run the caller cannot read.

    This used to "degrade to a resume": the launch answered 200 with the other operator's
    run, the client navigated to ``/runs/<that id>``, and every follow-up request 403'd into
    "Unable to load workspace data". Refusing here is the honest answer, and the distinct
    code lets the catalogue explain it. Nothing is destroyed either way.
    """
    existing = _existing_run(owner_user_id=OWNER)
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    with pytest.raises(SimulationError) as excinfo:
        _create(service, uow, restart_existing=True, owner_user_id=OTHER)

    assert excinfo.value.code is SimulationErrorCode.UNAUTHORIZED
    # The refused run's id must not travel back to the caller: handing over an id the
    # client cannot read, and would navigate to, is the whole of BUG-001.
    assert existing.id not in str(excinfo.value.details or {})
    assert existing.id not in excinfo.value.message
    assert uow.runs.deleted == []


def test_operator_starting_the_tutorial_after_another_identity_owns_it_is_refused() -> None:
    """BUG-001: a pinned-seed launch must never resolve to a run the caller cannot read.

    The reported failure was an operator whose "Start new run" resolved to a run owned by
    ``user:acct_…`` — a different identity — and answered 200 with ``replayed: true``. The
    launch must fail loudly instead, whether or not ``restartExisting`` was asked for. The
    live tutorial no longer reaches this path (the web client derives a per-operator seed, so
    each operator's training run is their own), but the guard stays for any scenario that
    pins a shared seed.
    """
    existing = _existing_run(owner_user_id="user:acct_9020b4189b4c9d8b620eb455")
    uow = _FakeUnitOfWork(runs=_FakeRunRepository(run=existing))
    service = RunCommandService(workspace_root=Path("."))

    for restart_existing in (False, True):
        with pytest.raises(SimulationError) as excinfo:
            _create(
                service,
                uow,
                restart_existing=restart_existing,
                owner_user_id="user:operator-alpha",
            )
        assert excinfo.value.code is SimulationErrorCode.UNAUTHORIZED

    assert uow.runs.deleted == []


# --- idempotency keys are scoped to the actor -------------------------------------


def test_create_idempotency_key_is_scoped_to_actor_and_scenario() -> None:
    """One client-chosen key must not address another identity's (or scenario's) record."""
    base = {"idempotency_key": "launch-key-1", "scenario_package_path": FIXTURE_PACKAGE}
    mine = scoped_create_idempotency_key(owner_user_id=OWNER, **base)

    assert mine != scoped_create_idempotency_key(owner_user_id=OTHER, **base)
    assert mine != scoped_create_idempotency_key(owner_user_id=None, **base)
    assert mine != scoped_create_idempotency_key(
        idempotency_key="launch-key-1",
        owner_user_id=OWNER,
        scenario_package_path="scenarios/other",
    )
    # Stable for the same actor, so a double-clicked launch still replays rather than
    # creating a second run.
    assert mine == scoped_create_idempotency_key(owner_user_id=OWNER, **base)
    # `idempotency_records.idempotency_key` is bounded at 256 characters.
    assert len(mine) <= 256


def test_a_shared_client_key_cannot_replay_another_identitys_run() -> None:
    """The stored key is namespaced, so the lookup misses instead of replaying."""
    existing = _existing_run(owner_user_id=OWNER)
    recorded_key = scoped_create_idempotency_key(
        idempotency_key="launch-key-1",
        owner_user_id=OWNER,
        scenario_package_path=FIXTURE_PACKAGE,
    )
    uow = _FakeUnitOfWork(
        runs=_FakeRunRepository(run=existing),
        idempotency=_FakeIdempotencyRepository(records={recorded_key: existing.id}),
    )
    service = RunCommandService(workspace_root=Path("."))

    # The owner replaying their own key still gets their run back.
    response = _create(service, uow, restart_existing=False, owner_user_id=OWNER)
    assert response.run.id == existing.id
    assert uow.idempotency.looked_up == [recorded_key]

    # The same key sent by a different identity resolves to no record at all, so the launch
    # falls through to the derived-run guard rather than replaying someone else's run.
    with pytest.raises(SimulationError) as excinfo:
        _create(service, uow, restart_existing=False, owner_user_id=OTHER)
    assert excinfo.value.code is SimulationErrorCode.UNAUTHORIZED
    assert uow.idempotency.looked_up[-1] != recorded_key


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
