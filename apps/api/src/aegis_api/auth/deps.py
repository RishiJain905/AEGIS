"""FastAPI authentication and authorization dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from aegis_contracts import (
    AegisSettings,
    ApiErrorEnvelopeV1,
    AuthenticatedActorV1,
    PermissionV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from aegis_api.auth.service import AuthService, AuthServiceError
from aegis_api.db.session import get_db_session_maker

CurrentActor = AuthenticatedActorV1


class AuthDependencyError(Exception):
    def __init__(self, exc: AuthServiceError) -> None:
        super().__init__(exc.message)
        self.exc = exc


def auth_error_response(exc: AuthServiceError) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=exc.code.value,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(by_alias=True))


def get_auth_service(request: Request) -> AuthService:
    settings: AegisSettings = request.app.state.settings
    return AuthService(session_ttl_seconds=settings.AEGIS_SESSION_TTL_SECONDS)


async def optional_actor(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedActorV1 | None:
    settings: AegisSettings = request.app.state.settings
    raw_token = request.cookies.get(settings.AEGIS_SESSION_COOKIE_NAME)
    if not raw_token:
        return None
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await auth_service.resolve_actor_from_token(uow, raw_token=raw_token)
    except AuthServiceError:
        return None


async def require_actor(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedActorV1:
    settings: AegisSettings = request.app.state.settings
    raw_token = request.cookies.get(settings.AEGIS_SESSION_COOKIE_NAME)
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            actor = await auth_service.resolve_actor_from_token(uow, raw_token=raw_token)
            if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                session = await auth_service.get_session_info(uow, session_id=actor.session_id)
                header_csrf = request.headers.get(settings.AEGIS_CSRF_HEADER_NAME)
                auth_service.validate_csrf(
                    session_csrf=session.csrf_token,
                    header_csrf=header_csrf,
                )
            try:
                from aegis_contracts.observability import ActorKindV1
                from aegis_observability.middleware import bind_actor_context

                primary_role = actor.roles[0].value if actor.roles else None
                bind_actor_context(
                    actor_id=actor.user_id,
                    actor_role=primary_role,
                    actor_kind=ActorKindV1.USER,
                )
            except Exception:  # noqa: BLE001 — telemetry must not break auth
                pass
            return actor
    except AuthServiceError as exc:
        raise AuthDependencyError(exc) from exc


def require_permission(
    permission: PermissionV1,
    *,
    resource_type: str | None = None,
    resource_id_param: str | None = None,
) -> Callable[..., Awaitable[AuthenticatedActorV1]]:
    async def _dependency(
        request: Request,
        actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
        auth_service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> AuthenticatedActorV1:
        resource_id = None
        if resource_id_param is not None:
            resource_id = request.path_params.get(resource_id_param)
        try:
            async with PostgresUnitOfWork(get_db_session_maker()) as uow:
                await auth_service.authorize(
                    uow,
                    actor=actor,
                    permission=permission,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request_id=request.headers.get("X-Request-Id"),
                )
        except AuthServiceError as exc:
            raise AuthDependencyError(exc) from exc
        return actor

    # Expose the required permission for static introspection (route-guard audits
    # in tests walk the dependant tree and read this attribute).
    _dependency.required_permission = permission  # type: ignore[attr-defined]
    return _dependency
