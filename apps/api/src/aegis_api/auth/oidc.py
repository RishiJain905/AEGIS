"""Provider-neutral OIDC authorization-code adapter."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from aegis_contracts import AegisSettings, AuthErrorCode


@dataclass(frozen=True)
class OidcTokenClaims:
    issuer: str
    subject: str
    email: str | None
    name: str | None
    audience: str


class OidcProvider(Protocol):
    def build_authorize_url(self, *, state: str, nonce: str, code_challenge: str) -> str: ...

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
    ) -> OidcTokenClaims: ...


class ConfiguredOidcProvider:
    """OIDC authorization-code + PKCE adapter using discovery-style config."""

    def __init__(self, settings: AegisSettings) -> None:
        self._settings = settings

    def build_authorize_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        if not self._settings.AEGIS_OIDC_ENABLED:
            raise AuthOidcError("OIDC is not enabled")
        if not self._settings.AEGIS_OIDC_ISSUER or not self._settings.AEGIS_OIDC_CLIENT_ID:
            raise AuthOidcError("OIDC issuer and client id are required")
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._settings.AEGIS_OIDC_CLIENT_ID,
                "redirect_uri": self._settings.AEGIS_OIDC_REDIRECT_URI,
                "scope": self._settings.AEGIS_OIDC_SCOPES,
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._settings.AEGIS_OIDC_ISSUER.rstrip('/')}/authorize?{query}"

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
    ) -> OidcTokenClaims:
        # Production deployments plug a real HTTP JWKS/token exchange here.
        # Without configured credentials this adapter fails closed.
        _ = (code, code_verifier)
        if not self._settings.AEGIS_OIDC_ENABLED:
            raise AuthOidcError("OIDC is not enabled")
        raise AuthOidcError(
            "OIDC token exchange requires a configured identity provider adapter"
        )


class FakeOidcProvider:
    """Test-only OIDC provider that mints deterministic claims for a code."""

    def __init__(self, *, issuer: str, audience: str) -> None:
        self._issuer = issuer
        self._audience = audience

    def build_authorize_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
            }
        )
        return f"{self._issuer}/authorize?{query}"

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
    ) -> OidcTokenClaims:
        _ = code_verifier
        if not code.startswith("oidc-code:"):
            raise AuthOidcError("Invalid authorization code")
        subject = code.removeprefix("oidc-code:")
        return OidcTokenClaims(
            issuer=self._issuer,
            subject=subject,
            email=f"{subject}@example.test",
            name=f"OIDC {subject}",
            audience=self._audience,
        )


class AuthOidcError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = AuthErrorCode.OIDC_FAILED
        self.message = message


def create_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        hashlib.sha256(verifier.encode("utf-8")).digest().hex()
    )  # hex challenge acceptable for local adapter tests
    return verifier, challenge


def create_oidc_provider(settings: AegisSettings) -> OidcProvider:
    if settings.AEGIS_OIDC_ENABLED:
        return ConfiguredOidcProvider(settings)
    return ConfiguredOidcProvider(settings)
