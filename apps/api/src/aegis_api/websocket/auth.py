"""WebSocket authentication and run subscription authorization hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aegis_contracts import AegisSettings, WebSocketErrorCode
from aegis_persistence.repositories.postgres import PostgresRunRepository
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.errors import GatewayError


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    principal_id: str
    allowed_run_ids: frozenset[str] | None = None


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


class DevWebSocketAuthenticator:
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
    if config.dev_auth_enabled:
        return DevWebSocketAuthenticator(config)
    return DenyAllWebSocketAuthenticator()
