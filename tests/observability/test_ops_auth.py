"""Authorization unit proof for protected observability endpoints."""

from __future__ import annotations

import pytest
from aegis_api.auth.deps import AuthDependencyError, require_permission
from aegis_api.auth.service import AuthServiceError
from aegis_contracts import AuthErrorCode, PermissionV1


def test_admin_manage_permission_dependency_factory() -> None:
    dep = require_permission(PermissionV1.ADMIN_MANAGE)
    assert callable(dep)


@pytest.mark.asyncio
async def test_auth_dependency_error_maps_unauthenticated() -> None:
    exc = AuthDependencyError(
        AuthServiceError(
            code=AuthErrorCode.UNAUTHENTICATED,
            message="Authentication required",
            status_code=401,
        )
    )
    assert exc.exc.status_code == 401
    assert exc.exc.code == AuthErrorCode.UNAUTHENTICATED
