"""Per-user cloud model-provider credential storage.

Every method takes ``user_id`` first and filters on it. That is the ownership rule of
this table expressed in its only access path: there is no "fetch by provider" here, so
no caller can accidentally hand one operator another's subscription key.

Rows are read and written as ORM rows rather than contracts on purpose — the ciphertext
must never reach a contract, and the only contract in this area
(``ProviderCredentialStatusV1``) is assembled by the API from the non-secret columns.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.credentials import (
    CREDENTIAL_ENCRYPTION_ALGORITHM,
    decrypt_api_key,
)
from aegis_persistence.orm.tables import AuthUserProviderCredentialRow


class PostgresProviderCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, provider: str) -> AuthUserProviderCredentialRow | None:
        """The stored row for one user's provider, or ``None`` if they have not connected it."""
        return await self._session.get(AuthUserProviderCredentialRow, (user_id, provider))

    async def list_status(self, user_id: str) -> list[AuthUserProviderCredentialRow]:
        """Every provider this user has connected, ordered by provider id."""
        result = await self._session.execute(
            select(AuthUserProviderCredentialRow)
            .where(AuthUserProviderCredentialRow.user_id == user_id)
            .order_by(AuthUserProviderCredentialRow.provider)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        user_id: str,
        provider: str,
        ciphertext: bytes,
        key_hint: str,
        verified_at: datetime | None,
        now: datetime,
        algorithm: str = CREDENTIAL_ENCRYPTION_ALGORITHM,
    ) -> AuthUserProviderCredentialRow:
        """Connect or replace this user's key for one provider.

        Reconnecting overwrites in place, keeping ``created_at`` as the moment the
        provider was first connected. The previous ciphertext is not retained anywhere:
        a replaced key is gone.
        """
        row = await self.get(user_id, provider)
        if row is None:
            row = AuthUserProviderCredentialRow(
                user_id=user_id,
                provider=provider,
                ciphertext=ciphertext,
                key_hint=key_hint,
                algorithm=algorithm,
                verified_at=verified_at,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.ciphertext = ciphertext
            row.key_hint = key_hint
            row.algorithm = algorithm
            row.verified_at = verified_at
            row.updated_at = now
        await self._session.flush()
        return row

    async def delete(self, user_id: str, provider: str) -> bool:
        """Disconnect a provider. ``False`` means there was nothing stored to remove."""
        row = await self.get(user_id, provider)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def get_decrypted_api_key(
        self,
        user_id: str,
        provider: str,
        *,
        encryption_key: str,
    ) -> str | None:
        """This user's plaintext key for one provider, for immediate use.

        ``None`` means no credential is stored — a distinct outcome from a stored
        credential that will not decrypt, which raises ``CredentialDecryptError`` so a
        rotated or corrupted encryption key surfaces as a failure rather than as a
        silently unconfigured provider.

        The returned string must not be logged, persisted, or copied into a request
        payload; hand it straight to the provider client that needs it.
        """
        row = await self.get(user_id, provider)
        if row is None:
            return None
        return decrypt_api_key(row.ciphertext, key=encryption_key)
