"""Tests for the long-running simulator container role."""

from __future__ import annotations

from aegis_simulation.runner import _run_service


class StopOnFirstWait:
    def wait(self, timeout_seconds: float) -> bool:
        assert timeout_seconds == 60.0
        return True


def test_simulator_service_waits_for_shutdown_signal() -> None:
    _run_service(stop_event=StopOnFirstWait())  # type: ignore[arg-type]
