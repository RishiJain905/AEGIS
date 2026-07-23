"""Regression guard for AEGIS-OITB-001 (mutating routes reachable read-only).

These tests are fully offline: they introspect the FastAPI dependant tree of the
built app (no database, no lifespan) and assert that every state-mutating route
requires a permission a read-only VIEWER does not hold. ``require_permission``
tags its dependency closure with ``required_permission`` so the guard set for a
route can be recovered statically.

The audit is data-driven so a *newly added* mutating route mounted under a
read-only permission (the exact OITB-001 defect) fails this test automatically.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from aegis_api.main import create_app
from aegis_contracts import (
    AegisEnvironment,
    AegisSettings,
    PermissionV1,
    PlatformRoleV1,
)
from aegis_policy.authz import ROLE_PERMISSION_MATRIX
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Routes that are intentionally unauthenticated (login/logout/session bootstrap).
_PUBLIC_PREFIXES = ("/api/v1/auth",)

# Mutating routes that are deliberately reachable with investigation:read because
# they are verified side-effect-free (pure compute over persisted events, no UoW,
# no writes). See features/router.py: compute_features / parity_check never persist.
_INTENTIONAL_VIEWER_READABLE: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/v1/features/compute"),
        ("POST", "/api/v1/features/parity-check"),
        # POST only to carry the search-filter body; console/service.py search_events is a
        # pure cursor-paged projection over the events table (no UoW writes, no events).
        ("POST", "/api/v1/runs/{run_id}/console/events/search"),
        # POST only to carry the counterfactual request body; ghost_engine runs an isolated
        # in-memory re-simulation and never appends events, writes snapshots, raises alerts,
        # or touches the outbox — it only reads persisted run history.
        ("POST", "/api/v1/runs/{run_id}/ghost"),
    }
)

# Exact permission each OITB-001 route must enforce (locks the chosen fix in place).
_EXPECTED_ROUTE_PERMISSIONS: dict[tuple[str, str], PermissionV1] = {
    ("POST", "/api/v1/detection/evaluate"): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/models/score"): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/models/verify-artifact"): PermissionV1.ADMIN_MANAGE,
    ("POST", "/api/v1/risk/compute"): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/agents/harness/seed"): PermissionV1.INVESTIGATION_TRIGGER,
    (
        "POST",
        "/api/v1/incidents/{incident_id}/agent-sessions",
    ): PermissionV1.INVESTIGATION_TRIGGER,
    (
        "POST",
        "/api/v1/runs/{run_id}/agent-sessions",
    ): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/agent-sessions/{session_id}/tasks"): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/agent-sessions/{session_id}/cancel"): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/agent-tasks/{task_id}/retry"): PermissionV1.INVESTIGATION_TRIGGER,
    ("POST", "/api/v1/realtime/backfill"): PermissionV1.ADMIN_MANAGE,
}


def _settings() -> AegisSettings:
    return AegisSettings(
        AEGIS_ENV=AegisEnvironment.TEST,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="aegis",
        POSTGRES_USER="aegis",
        POSTGRES_PASSWORD="aegis",
        REDIS_URL="redis://localhost:6379/0",
        S3_ENDPOINT="http://localhost:9000",
        S3_ACCESS_KEY="minio",
        S3_SECRET_KEY="minio123",
        S3_BUCKET="aegis",
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_ENABLED=False,
        AEGIS_WS_DEV_AUTH_ENABLED=False,
        AEGIS_OIDC_ENABLED=False,
        AEGIS_CORS_ALLOWED_ORIGINS="http://localhost:3000",
    )


def _iter_dependants(dependant: Dependant) -> Iterator[Dependant]:
    yield dependant
    for sub in dependant.dependencies:
        yield from _iter_dependants(sub)


def _mount_permissions(wrapper: object) -> set[PermissionV1]:
    # Router-mount dependencies (``app.include_router(..., dependencies=...)``) are
    # kept on the ``_IncludedRouter`` wrapper's ``include_context`` in this app rather
    # than merged into each route's dependant; pull the guarded permissions from there.
    permissions: set[PermissionV1] = set()
    context = getattr(wrapper, "include_context", None)
    for depends in getattr(context, "dependencies", None) or []:
        permission = getattr(getattr(depends, "dependency", None), "required_permission", None)
        if permission is not None:
            permissions.add(permission)
    return permissions


def _walk_api_routes(
    routes: object,
    inherited: frozenset[PermissionV1],
) -> Iterator[tuple[APIRoute, frozenset[PermissionV1]]]:
    # The app mounts each included router behind an ``_IncludedRouter`` wrapper that
    # exposes the concrete sub-router via ``original_router`` rather than flattening
    # routes into ``app.routes``; recurse through those wrappers, accumulating each
    # mount's dependency permissions so they apply to every route beneath it.
    for route in routes:  # type: ignore[union-attr]
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            mount_perms = inherited | frozenset(_mount_permissions(route))
            yield from _walk_api_routes(original_router.routes, mount_perms)
        elif isinstance(route, APIRoute):
            yield route, inherited


def _route_permissions(route: APIRoute, mount_perms: frozenset[PermissionV1]) -> set[PermissionV1]:
    permissions = set(mount_perms)
    for dependant in _iter_dependants(route.dependant):
        permission = getattr(dependant.call, "required_permission", None)
        if permission is not None:
            permissions.add(permission)
    return permissions


def _mutating_routes() -> list[tuple[APIRoute, frozenset[PermissionV1]]]:
    app = create_app(_settings())
    return [
        (route, mount_perms)
        for route, mount_perms in _walk_api_routes(app.routes, frozenset())
        if (route.methods or set()) & _MUTATING_METHODS
    ]


def _mutating_verb(route: APIRoute) -> str:
    return sorted((route.methods or set()) & _MUTATING_METHODS)[0]


def _viewer_permissions() -> frozenset[PermissionV1]:
    return ROLE_PERMISSION_MATRIX[PlatformRoleV1.VIEWER]


def test_every_mutating_route_requires_a_write_permission_viewer_lacks() -> None:
    viewer = _viewer_permissions()
    admin = ROLE_PERMISSION_MATRIX[PlatformRoleV1.ADMIN]

    offenders: list[str] = []
    for route, mount_perms in _mutating_routes():
        if route.path.startswith(_PUBLIC_PREFIXES):
            continue
        key = (_mutating_verb(route), route.path)
        required = _route_permissions(route, mount_perms)

        if key in _INTENTIONAL_VIEWER_READABLE:
            # Must still require authentication + a permission (read is acceptable);
            # it simply is not a *write* gate because the handler is side-effect-free.
            assert required, f"{key} lost its authorization guard entirely"
            continue

        # Core OITB-001 assertion: a VIEWER (read-only) cannot satisfy the guard.
        if required.issubset(viewer):
            guard = sorted(p.value for p in required)
            offenders.append(f"{key} guarded only by read permissions {guard}")
            continue

        # Sanity: an ADMIN (all permissions) can still satisfy the guard.
        assert required.issubset(admin), f"{key} requires a permission outside the role model"

    assert not offenders, (
        "Mutating routes reachable with read-only permission:\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    ("verb", "path", "expected"),
    [(verb, path, perm) for (verb, path), perm in _EXPECTED_ROUTE_PERMISSIONS.items()],
)
def test_named_oitb001_routes_enforce_expected_permission(
    verb: str,
    path: str,
    expected: PermissionV1,
) -> None:
    matches = [
        (route, mount_perms)
        for route, mount_perms in _mutating_routes()
        if route.path == path and verb in (route.methods or set())
    ]
    assert matches, f"Route {verb} {path} not found (renamed or removed?)"

    route, mount_perms = matches[0]
    required = _route_permissions(route, mount_perms)
    assert expected in required, (
        f"{verb} {path} must enforce {expected.value}; found {sorted(p.value for p in required)}"
    )

    viewer = _viewer_permissions()
    assert not required.issubset(viewer), f"{verb} {path} is reachable by a read-only VIEWER"


def test_features_compute_routes_are_side_effect_free_read_only() -> None:
    # Documents the deliberate exception: these persist nothing, so investigation:read
    # is acceptable. If they ever gain a write, they leave this allowlist and the
    # audit above will demand a write permission.
    viewer = _viewer_permissions()
    seen: set[tuple[str, str]] = set()
    for route, mount_perms in _mutating_routes():
        key = (_mutating_verb(route), route.path)
        if key not in _INTENTIONAL_VIEWER_READABLE:
            continue
        seen.add(key)
        required = _route_permissions(route, mount_perms)
        read_gates = {
            PermissionV1.INVESTIGATION_READ,
            PermissionV1.RUNS_READ,
            PermissionV1.SCORING_READ,
        }
        assert required & read_gates, f"{key} must still enforce a read permission"
        assert required.issubset(viewer), f"{key} unexpectedly demands a permission VIEWER lacks"
    assert seen == set(_INTENTIONAL_VIEWER_READABLE), "features allowlist drifted from live routes"
