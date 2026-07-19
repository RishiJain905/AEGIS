"""Docker gating and bounded service controls for failure injection."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import pytest
from tests.integration.conftest import (  # noqa: F401
    db_engine,
    db_session,
    migrated_database,
    postgres_available,
    redis_available,
    redis_client,
    session_maker,
    settings,
    unit_of_work,
)

_ENABLED = os.environ.get("AEGIS_RUN_FAILURE_INJECTION") == "1"
_SKIP_REASON = (
    "failure injection requires Docker and AEGIS_RUN_FAILURE_INJECTION=1; "
    "run scripts/run_release_validation.* --environment local"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _ENABLED:
        return
    skip = pytest.mark.skip(reason=_SKIP_REASON)
    for item in items:
        if item.get_closest_marker("failure_injection"):
            item.add_marker(skip)


def wait_until(
    condition: Callable[[], bool],
    *,
    timeout_seconds: float = 30,
    description: str,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if condition():
            return
        threading.Event().wait(0.2)
    pytest.fail(f"Timed out waiting for {description} after {timeout_seconds}s")


@dataclass
class ComposeController:
    stopped: set[str] = field(default_factory=set)

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "compose", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def stop(self, service: str) -> None:
        result = self._run("stop", "--timeout", "10", service)
        assert result.returncode == 0, result.stderr
        self.stopped.add(service)

    def start(self, service: str) -> None:
        result = self._run("start", service)
        assert result.returncode == 0, result.stderr
        self.stopped.discard(service)
        wait_until(
            lambda: service in self._run("ps", "--status", "running", "--services").stdout,
            description=f"{service} container to run",
        )

    def restart(self, service: str) -> None:
        result = self._run("restart", "--timeout", "10", service)
        assert result.returncode == 0, result.stderr
        wait_until(
            lambda: service in self._run("ps", "--status", "running", "--services").stdout,
            description=f"{service} container to restart",
        )


@pytest.fixture(scope="session")
def docker_available() -> None:
    if not _ENABLED:
        pytest.skip(_SKIP_REASON)
    try:
        result = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("failure injection skipped: Docker CLI/daemon is unavailable")
    if result.returncode != 0:
        pytest.skip("failure injection skipped: Docker daemon is unavailable")


@pytest.fixture
def compose_controller(docker_available: None) -> Iterator[ComposeController]:
    controller = ComposeController()
    yield controller
    for service in sorted(controller.stopped):
        controller.start(service)
