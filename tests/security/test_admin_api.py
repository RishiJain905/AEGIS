"""Admin console API guards and read-first behaviour (fully offline).

Covers three properties the admin surface must hold:
  * every ``/api/v1/admin/*`` route is guarded by ``admin:manage`` and is NOT
    reachable by a read-only VIEWER (server-enforced authorization);
  * the policy and users projections have the expected shapes;
  * ``/admin/settings`` never leaks secret material.

The guard checks introspect the built FastAPI dependant tree (no DB, no lifespan),
mirroring ``tests/security/test_authz_route_guards.py``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from aegis_api.admin.service import AdminService, user_to_model
from aegis_api.main import create_app
from aegis_contracts import (
    AegisEnvironment,
    AegisSettings,
    PermissionV1,
    PlatformRoleV1,
)
from aegis_model_provider.config import ProviderSettings
from aegis_policy.authz import ROLE_PERMISSION_MATRIX
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

_ADMIN_PREFIX = "/api/v1/admin"


def _settings(**overrides: object) -> AegisSettings:
    base: dict[str, object] = {
        "AEGIS_ENV": AegisEnvironment.TEST,
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "aegis",
        "POSTGRES_USER": "aegis",
        "POSTGRES_PASSWORD": "pg-secret-value-xyz",
        "REDIS_URL": "redis://localhost:6379/0",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_ACCESS_KEY": "minio",
        "S3_SECRET_KEY": "s3-secret-value-xyz",
        "S3_BUCKET": "aegis",
        "AEGIS_DEV_AUTH_ENABLED": False,
        "AEGIS_WS_ENABLED": False,
        "AEGIS_WS_DEV_AUTH_ENABLED": False,
        "AEGIS_OIDC_ENABLED": False,
        "AEGIS_CORS_ALLOWED_ORIGINS": "http://localhost:3000",
    }
    base.update(overrides)
    return AegisSettings(**base)  # type: ignore[arg-type]


def _iter_dependants(dependant: Dependant) -> Iterator[Dependant]:
    yield dependant
    for sub in dependant.dependencies:
        yield from _iter_dependants(sub)


def _mount_permissions(wrapper: object) -> set[PermissionV1]:
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


def _admin_routes() -> list[tuple[APIRoute, frozenset[PermissionV1]]]:
    app = create_app(_settings())
    return [
        (route, mount_perms)
        for route, mount_perms in _walk_api_routes(app.routes, frozenset())
        if route.path.startswith(_ADMIN_PREFIX)
    ]


def test_admin_routes_exist() -> None:
    paths = {route.path for route, _ in _admin_routes()}
    assert paths == {
        f"{_ADMIN_PREFIX}/users",
        f"{_ADMIN_PREFIX}/policy",
        f"{_ADMIN_PREFIX}/settings",
    }


def test_every_admin_route_requires_admin_manage() -> None:
    routes = _admin_routes()
    assert routes, "admin routes not mounted"
    viewer = ROLE_PERMISSION_MATRIX[PlatformRoleV1.VIEWER]
    for route, mount_perms in routes:
        required = _route_permissions(route, mount_perms)
        found = sorted(permission.value for permission in required)
        assert PermissionV1.ADMIN_MANAGE in required, (
            f"{route.path} is not guarded by admin:manage (found {found})"
        )
        # A read-only VIEWER (and every non-admin role) cannot satisfy the guard.
        assert not required.issubset(viewer), f"{route.path} reachable by a read-only VIEWER"


def test_non_admin_roles_cannot_satisfy_admin_manage() -> None:
    # admin:manage belongs to ADMIN only; every other role's grant is denied at
    # authorize() and returns 403 (Permission denied) for these routes.
    for role, permissions in ROLE_PERMISSION_MATRIX.items():
        if role is PlatformRoleV1.ADMIN:
            assert PermissionV1.ADMIN_MANAGE in permissions
        else:
            assert PermissionV1.ADMIN_MANAGE not in permissions


def test_policy_snapshot_shape() -> None:
    snapshot = AdminService().build_policy_snapshot()
    roles = {entry.role for entry in snapshot.roles}
    assert roles == {role.value for role in PlatformRoleV1}

    admin_entry = next(
        entry for entry in snapshot.roles if entry.role == PlatformRoleV1.ADMIN.value
    )
    assert PermissionV1.ADMIN_MANAGE.value in admin_entry.permissions

    viewer_entry = next(
        entry for entry in snapshot.roles if entry.role == PlatformRoleV1.VIEWER.value
    )
    assert PermissionV1.ADMIN_MANAGE.value not in viewer_entry.permissions

    assert PermissionV1.ADMIN_MANAGE.value in snapshot.permissions
    assert snapshot.approver_roles == ["incident_commander", "security_lead"]
    # Class 2/3 require approval; class 0/1 do not.
    approval_by_class = {
        entry.action_class: entry.approval_required for entry in snapshot.action_classes
    }
    assert approval_by_class == {
        "class_0": False,
        "class_1": False,
        "class_2": True,
        "class_3": True,
    }


def test_user_projection_derives_permissions() -> None:
    admin = user_to_model(
        user_id="user:admin-alpha",
        display_name="Admin Alpha",
        status="active",
        roles=[PlatformRoleV1.ADMIN],
    )
    assert PermissionV1.ADMIN_MANAGE.value in admin.permissions

    viewer = user_to_model(
        user_id="user:viewer-alpha",
        display_name="Viewer Alpha",
        status="active",
        roles=[PlatformRoleV1.VIEWER],
    )
    assert PermissionV1.ADMIN_MANAGE.value not in viewer.permissions
    assert viewer.roles == [PlatformRoleV1.VIEWER.value]


def test_settings_snapshot_excludes_secrets() -> None:
    settings = _settings(
        AEGIS_OIDC_CLIENT_SECRET="oidc-secret-value-xyz",
    )
    provider = ProviderSettings(
        AEGIS_PROVIDER_OPENAI_API_KEY="sk-provideropenaisecretvalue",
        AEGIS_PROVIDER_LOCAL_API_KEY="local-api-key-secret-xyz",
    )
    snapshot = AdminService().build_settings_snapshot(settings, provider, health={})
    serialized = json.dumps(snapshot.model_dump(by_alias=True))

    for secret in (
        "pg-secret-value-xyz",
        "s3-secret-value-xyz",
        "oidc-secret-value-xyz",
        "sk-provideropenaisecretvalue",
        "local-api-key-secret-xyz",
    ):
        assert secret not in serialized, f"secret material leaked into settings snapshot: {secret}"

    # Non-secret configuration is present.
    assert snapshot.version
    assert snapshot.provider["defaultProvider"] == provider.AEGIS_PROVIDER_DEFAULT.value
    assert snapshot.provider["localModel"] == provider.AEGIS_PROVIDER_LOCAL_MODEL
