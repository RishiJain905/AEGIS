"""Contract for the incident queue reads (BUG-010).

The triage queue used to be assembled client-side by fanning out over the run list:
one incidents request and one alerts request *per run*. At 16 runs that is 33
simultaneous requests against a 30-token burst limit, so the queue reliably 429'd and
the page rendered "Unable to load incidents" while the incidents themselves were fine.

The fix is a cross-run ``GET /api/v1/incidents``. These checks are offline — they
introspect the runs router and the repository, no app, no database — and pin the two
properties a fan-out could silently lose:

* the cross-run read exists, returns ``IncidentV1`` rows, and takes an authenticated
  actor;
* both reads stay run-visibility-scoped, so the queue cannot become a way to read
  another operator's incidents by skipping the per-run authorization.
"""

from __future__ import annotations

import inspect

import pytest
from aegis_api.runs.router import list_run_incidents, list_visible_incidents
from aegis_api.runs.router import router as runs_router
from aegis_contracts import IncidentV1
from aegis_persistence.repositories.postgres import PostgresIncidentRepository
from fastapi.routing import APIRoute

_CROSS_RUN_PATH = "/api/v1/incidents"
_RUN_SCOPED_PATH = "/api/v1/runs/{run_id}/incidents"


@pytest.fixture(scope="module")
def routes() -> dict[tuple[str, str], APIRoute]:
    return {
        (method, route.path): route
        for route in runs_router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_cross_run_incident_query_is_mounted(routes: dict[tuple[str, str], APIRoute]) -> None:
    """Without this route the client is forced back into the per-run fan-out."""
    assert ("GET", _CROSS_RUN_PATH) in routes


def test_cross_run_incident_query_returns_incident_contracts(
    routes: dict[tuple[str, str], APIRoute],
) -> None:
    route = routes[("GET", _CROSS_RUN_PATH)]
    assert route.response_model == list[IncidentV1]


def test_both_incident_queries_require_an_authenticated_actor(
    routes: dict[tuple[str, str], APIRoute],
) -> None:
    """The queue spans runs, so an unauthenticated read would expose every incident."""
    for path in (_CROSS_RUN_PATH, _RUN_SCOPED_PATH):
        signature = inspect.signature(routes[("GET", path)].endpoint)
        assert "actor" in signature.parameters, path


def test_cross_run_query_scopes_runs_the_same_way_the_run_list_does() -> None:
    """Admins see every run's incidents; everybody else only their own.

    Asserted on the source because the alternative — an unfiltered ``list_by_runs``
    over every run id — reads identically at the call site and would leak another
    operator's incidents into the queue.
    """
    source = inspect.getsource(list_visible_incidents)
    assert "actor_is_admin(actor)" in source
    assert "list_for_owner(actor.user_id)" in source


def test_run_scoped_query_keeps_its_owner_gate() -> None:
    source = inspect.getsource(list_run_incidents)
    assert "_authorize_run(run, actor, run_id)" in source


def test_repository_short_circuits_an_empty_run_set() -> None:
    """An actor with no runs must not issue an ``IN ()`` query for the queue."""
    source = inspect.getsource(PostgresIncidentRepository.list_by_runs)
    assert "if not run_ids:" in source
    assert "return []" in source
