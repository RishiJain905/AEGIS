"""Admin console HTTP routes.

Thin handlers delegating to :class:`AdminService`. Every route is mounted behind
``require_permission(admin:manage)`` in ``main.py`` — administration access is
enforced server-side, never by the UI alone.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from aegis_contracts import AegisSettings, PlatformRoleV1
from aegis_contracts.errors import ContractValidationError
from aegis_model_provider import load_provider_settings
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.health_probe import (
    ProviderProbeState,
    probe_model_provider,
)
from aegis_observability.health import evaluate_readiness
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from aegis_api.admin.models import (
    AdminCreateUserRequestV1,
    AdminPolicyResponseV1,
    AdminSettingsResponseV1,
    AdminUsersResponseV1,
    AdminUserV1,
)
from aegis_api.admin.service import AdminService, user_to_model
from aegis_api.auth.deps import get_auth_service
from aegis_api.auth.router import _error_response, _validation_error_response
from aegis_api.auth.service import AuthService, AuthServiceError
from aegis_api.db.session import db_session, get_db_session_maker
from aegis_api.observability.routes import collect_dependency_statuses

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=AdminUsersResponseV1)
async def list_users() -> AdminUsersResponseV1:
    async with db_session() as session:
        return await AdminService().list_users(session)


@router.post("/users", response_model=AdminUserV1)
async def create_user(
    request: Request,
    body: AdminCreateUserRequestV1,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> object:
    """Admin-only: provision a new credentialed account with the given roles.

    Mounted behind ``require_permission(admin:manage)`` in ``main.py``; a viewer or
    analyst can never reach it. The password is hashed with Argon2id and never
    stored in plaintext or echoed back.
    """
    try:
        roles = [PlatformRoleV1(role) for role in body.roles]
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"schemaVersion": 1, "code": "VALIDATION_FAILED", "message": str(exc)},
        )
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            user = await auth_service.register_credentialed_user(
                uow,
                username=body.username,
                password=body.password,
                display_name=body.display_name,
                roles=roles,
                request_id=request.headers.get("X-Request-Id"),
            )
        return user_to_model(
            user_id=user.user_id,
            display_name=user.display_name,
            status=user.status,
            roles=user.roles,
        )
    except ContractValidationError as exc:
        return _validation_error_response(exc)
    except AuthServiceError as exc:
        return _error_response(exc)


@router.get("/policy", response_model=AdminPolicyResponseV1)
async def get_policy() -> AdminPolicyResponseV1:
    return AdminService().build_policy_snapshot()


async def _model_provider_health(provider_settings: ProviderSettings) -> dict[str, object]:
    """Probe the model provider as a *separate* axis from infrastructure readiness.

    Deliberately not folded into ``evaluate_readiness``: AEGIS stays operable with
    the model down, so a dead provider must never make ``/ready`` (or this panel's
    infrastructure summary) report not-ready. The probe already fails soft; this
    second guard makes the admin route unbreakable even if the probe itself
    regresses.
    """
    try:
        result = await probe_model_provider(provider_settings)
        return result.to_payload()
    except Exception as exc:  # noqa: BLE001 — never 500 the admin page over a probe
        return {
            "provider": "unknown",
            "state": ProviderProbeState.FAILED.value,
            "baseUrl": None,
            "configuredModel": None,
            "reportedModels": [],
            "reportedModel": None,
            "configuredModelServed": None,
            "latencyMs": None,
            "checkedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "message": f"Provider health probe failed: {type(exc).__name__}",
        }


@router.get("/settings", response_model=AdminSettingsResponseV1)
async def get_settings(request: Request) -> AdminSettingsResponseV1:
    settings: AegisSettings = request.app.state.settings
    provider_settings = load_provider_settings()
    results = await collect_dependency_statuses(settings)
    health: dict[str, object] = {
        # Infrastructure axis only — postgres / redis / object storage.
        "status": evaluate_readiness(results).value,
        "dependencies": [result.to_status().model_dump(by_alias=True) for result in results],
        # Model axis, reported side by side and never merged into the above.
        "modelProvider": await _model_provider_health(provider_settings),
    }
    return AdminService().build_settings_snapshot(settings, provider_settings, health=health)
