"""The run's virtual simulation clock.

Every domain event carries two timestamps with distinct meaning (architecture contract
§7): ``sim_time`` is the run's VIRTUAL clock, ``recorded_at`` is the WALL-CLOCK instant
the event was persisted. Stamping ``sim_time`` with ``datetime.now()`` is a bug — it
drops wall-clock entries ("INCIDENT 05:30:33") into an operational chronicle whose other
rows sit at their true sim-time offsets ("00:12:00"), and drags the cockpit CLOCK
instrument with them.

The resolver lives in ``aegis_persistence`` rather than in any one service because the
callers span layers that may not import each other: the detection engine
(``aegis_incidents``), the agent runtime (``aegis_agents``), report generation
(``aegis_reports``), and the approval/operator-action routes in ``apps/api``. A copy per
caller is exactly how the wall-clock default crept back in the first time.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def run_sim_time(uow: PostgresUnitOfWork, run_id: str) -> datetime:
    """Current VIRTUAL sim-time of ``run_id`` — the clock domain events must carry.

    Falls back to wall-clock only when the run row is missing, which on a live path it
    never is: an event is always appended to a run that exists. The fallback keeps a
    half-seeded fixture from raising rather than making wall-clock a silent default —
    which is why builders take ``sim_time`` as a *required* argument and no builder calls
    this itself.
    """
    run = await uow.runs.get_by_id(run_id)
    return run.sim_time if run is not None else datetime.now(UTC)
