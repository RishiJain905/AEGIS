"""WebSocket authentication and run subscription authorization hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aegis_contracts import AegisSettings, PermissionV1, WebSocketErrorCode
from aegis_persistence.repositories.postgres import PostgresRunRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_api.auth.service import AuthService, AuthServiceError
from aegis_api.db.session import get_db_session_maker
from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.errors import GatewayError


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    principal_id: str
    allowed_run_ids: frozenset[str] | None = None
    permissions: frozenset[str] | None = None


class WebSocketAuthenticator(Protocol):
    async def authenticate(self, *, auth_token: str | None) -> AuthenticatedPrincipal: ...


class RunSubscriptionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        principal: AuthenticatedPrincipal,
        run_id: str,
        channel: str,
    ) -> None: ...


class SessionWebSocketAuthenticator:
    """Authenticate WebSocket hello frames using session or short-lived WS tickets."""

    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
        settings: AegisSettings,
    ) -> None:
        self._session_maker = session_maker
        self._auth_service = AuthService(session_ttl_seconds=settings.AEGIS_SESSION_TTL_SECONDS)

    async def authenticate(self, *, auth_token: str | None) -> AuthenticatedPrincipal:
        try:
            async with PostgresUnitOfWork(self._session_maker) as uow:
                actor = await self._auth_service.resolve_actor_from_ws_ticket(
                    uow,
                    ticket=auth_token,
                )
                await self._auth_service.authorize(
                    uow,
                    actor=actor,
                    permission=PermissionV1.WS_SUBSCRIBE,
                )
                grants = await uow.auth.list_grants_for_user(actor.user_id)
                allowed_run_ids: frozenset[str] | None = None
                run_grants = [g for g in grants if g.resource_type == "run"]
                if run_grants:
                    allowed_run_ids = frozenset(g.resource_id for g in run_grants)
                return AuthenticatedPrincipal(
                    principal_id=actor.user_id,
                    allowed_run_ids=allowed_run_ids,
                    permissions=frozenset(p.value for p in actor.permissions),
                )
        except AuthServiceError as exc:
            raise GatewayError(
                code=WebSocketErrorCode.WS_UNAUTHORIZED,
                message=exc.message,
            ) from exc


class DevWebSocketAuthenticator:
    """Legacy Phase 12 hook retained for isolated unit tests only."""

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    async def authenticate(self, *, auth_token: str | None) -> AuthenticatedPrincipal:
        if not self._config.dev_auth_enabled:
            raise GatewayError(
                code=WebSocketErrorCode.WS_UNAUTHORIZED,
                message="WebSocket authentication is not configured",
            )
        if auth_token != self._config.dev_auth_token:
            raise GatewayError(
                code=WebSocketErrorCode.WS_UNAUTHORIZED,
                message="Invalid authentication token",
            )
        return AuthenticatedPrincipal(principal_id="dev-operator", allowed_run_ids=None)


class DenyAllWebSocketAuthenticator:
    async def authenticate(self, *, auth_token: str | None) -> AuthenticatedPrincipal:
        raise GatewayError(
            code=WebSocketErrorCode.WS_UNAUTHORIZED,
            message="WebSocket authentication is not configured",
        )


class DevRunSubscriptionAuthorizer:
    def __init__(self, session: AsyncSession) -> None:
        self._runs = PostgresRunRepository(session)

    async def authorize(
        self,
        *,
        principal: AuthenticatedPrincipal,
        run_id: str,
        channel: str,
    ) -> None:
        _ = channel
        if (
            principal.permissions is not None
            and PermissionV1.WS_SUBSCRIBE.value not in principal.permissions
        ):
            raise GatewayError(
                code=WebSocketErrorCode.WS_FORBIDDEN,
                message=f"Principal {principal.principal_id} lacks ws:subscribe",
            )
        if principal.allowed_run_ids is not None and run_id not in principal.allowed_run_ids:
            raise GatewayError(
                code=WebSocketErrorCode.WS_FORBIDDEN,
                message=f"Principal {principal.principal_id} cannot subscribe to run {run_id}",
            )
        run = await self._runs.get_by_id(run_id)
        if run is None:
            raise GatewayError(
                code=WebSocketErrorCode.WS_UNKNOWN_RUN,
                message=f"Unknown run: {run_id}",
            )


class DenyUnauthorizedRunAuthorizer:
    """Authorizer that rejects a specific run id for testing."""

    def __init__(self, session: AsyncSession, *, denied_run_ids: frozenset[str]) -> None:
        self._inner = DevRunSubscriptionAuthorizer(session)
        self._denied_run_ids = denied_run_ids

    async def authorize(
        self,
        *,
        principal: AuthenticatedPrincipal,
        run_id: str,
        channel: str,
    ) -> None:
        if run_id in self._denied_run_ids:
            raise GatewayError(
                code=WebSocketErrorCode.WS_FORBIDDEN,
                message=f"Subscription to run {run_id} is not permitted",
            )
        await self._inner.authorize(
            principal=principal,
            run_id=run_id,
            channel=channel,
        )


def build_authenticator(settings: AegisSettings, config: GatewayConfig) -> WebSocketAuthenticator:
    if (
        config.dev_auth_enabled
        and settings.AEGIS_ENV.value == "test"
        and not settings.AEGIS_DEV_AUTH_ENABLED
    ):
        return DevWebSocketAuthenticator(config)
    try:
        session_maker = get_db_session_maker()
    except Exception:
        if config.dev_auth_enabled:
            return DevWebSocketAuthenticator(config)
        return DenyAllWebSocketAuthenticator()
    return SessionWebSocketAuthenticator(session_maker=session_maker, settings=settings)
