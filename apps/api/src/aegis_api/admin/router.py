"""Admin console HTTP routes.

Thin handlers delegating to :class:`AdminService`. Every route is mounted behind
``require_permission(admin:manage)`` in ``main.py`` — administration access is
enforced server-side, never by the UI alone.
"""

from __future__ import annotations

from aegis_contracts import AegisSettings
from aegis_model_provider import load_provider_settings
from aegis_observability.health import evaluate_readiness
from fastapi import APIRouter, Request

from aegis_api.admin.models import (
    AdminPolicyResponseV1,
    AdminSettingsResponseV1,
    AdminUsersResponseV1,
)
from aegis_api.admin.service import AdminService
from aegis_api.db.session import db_session
from aegis_api.observability.routes import collect_dependency_statuses

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=AdminUsersResponseV1)
async def list_users() -> AdminUsersResponseV1:
    async with db_session() as session:
        return await AdminService().list_users(session)


@router.get("/policy", response_model=AdminPolicyResponseV1)
async def get_policy() -> AdminPolicyResponseV1:
    return AdminService().build_policy_snapshot()


@router.get("/settings", response_model=AdminSettingsResponseV1)
async def get_settings(request: Request) -> AdminSettingsResponseV1:
    settings: AegisSettings = request.app.state.settings
    provider_settings = load_provider_settings()
    results = await collect_dependency_statuses(settings)
    health: dict[str, object] = {
        "status": evaluate_readiness(results).value,
        "dependencies": [result.to_status().model_dump(by_alias=True) for result in results],
    }
    return AdminService().build_settings_snapshot(settings, provider_settings, health=health)
