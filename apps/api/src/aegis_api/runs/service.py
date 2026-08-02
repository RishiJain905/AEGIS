"""Process-wide shared simulation run command service.

The API process is the single writer for simulation run state: it owns exactly one
:class:`RunCommandService` whose in-memory runtime cache is shared by the manual
lifecycle routes (``/runs/{id}/step|pause|resume|stop``) and the background tick engine.
Both serialize on the service's per-run locks (``lock_for``) before mutating a cached
runtime, which is what makes the single-writer guarantee hold across concurrent requests
and ticks.

Approval execution (``aegis_api.approvals.service``) shares this instance too. It used to
keep an isolated one so a rolled-back approval could not dirty the shared runtime, but an
executed containment then mutated a runtime nobody stepped and nothing ever recovered it:
a cached runtime advances its ``next_sequence`` past out-of-band events without applying
them, so the next checkpoint stranded the effect behind the restore cursor permanently.
Isolating an asset changed neither the world nor the graph. Rollback isolation is provided
instead by the executing routes, which hold ``lock_for(run_id)`` across their transaction
and evict the cached runtime — inside the lock — if it fails.
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
