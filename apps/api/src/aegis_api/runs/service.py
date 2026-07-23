"""Process-wide shared simulation run command service.

The API process is the single writer for simulation run state: it owns exactly one
:class:`RunCommandService` whose in-memory runtime cache is shared by the manual
lifecycle routes (``/runs/{id}/step|pause|resume|stop``) and the background tick engine.
Both serialize on the service's per-run locks (``lock_for``) before mutating a cached
runtime, which is what makes the single-writer guarantee hold across concurrent requests
and ticks.

Approval execution (``aegis_api.approvals.service``) deliberately keeps its own isolated
:class:`RunCommandService` instance: an approval transaction can roll back, and a rolled
back mutation must not dirty the shared cached runtime. Because approvals mutate a
separate runtime object, they never interleave on the *same* runtime; the tick engine
reconciles any externally-appended effect events by evicting and re-restoring the run on
the next cycle (see :mod:`aegis_api.runs.tick_engine`).
"""

from __future__ import annotations

from pathlib import Path

from aegis_simulation.run_command_service import RunCommandService

# apps/api/src/aegis_api/runs/service.py -> repo root is five parents up.
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]

_run_command_service = RunCommandService(workspace_root=WORKSPACE_ROOT)


def get_run_command_service() -> RunCommandService:
    """Return the process-wide shared run command service singleton."""
    return _run_command_service
