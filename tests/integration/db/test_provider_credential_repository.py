"""Per-user provider credential rows against real PostgreSQL.

The properties that matter here are ownership and replacement: one row per
``(user_id, provider)`` so reconnecting a key overwrites rather than accumulates, and
every read scoped to the asking user so one operator's subscription key can never be
listed — let alone decrypted — by another.

These tests create and remove only their own rows (no TRUNCATE), so they are safe to
run against a database a live stack is also using.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import PlatformRoleV1
from aegis_persistence.credentials import (
    CredentialDecryptError,
    derive_key_hint,
    encrypt_api_key,
    generate_encryption_key,
)
from aegis_persistence.orm.tables import AuthUserRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_OWNER = "user:provider-cred-owner"
_OTHER = "user:provider-cred-other"
_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


async def _seed_users(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with PostgresUnitOfWork(session_maker) as uow:
        for user_id in (_OWNER, _OTHER):
            await uow.auth.upsert_user(
                user_id=user_id,
                display_name=user_id,
                roles=[PlatformRoleV1.OPERATOR],
                now=_NOW,
            )


async def _drop_users(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.session.execute(
            delete(AuthUserRow).where(AuthUserRow.user_id.in_([_OWNER, _OTHER]))
        )


@pytest.fixture
async def seeded_users(session_maker: async_sessionmaker[AsyncSession]) -> None:
    await _drop_users(session_maker)
    await _seed_users(session_maker)
    yield
    await _drop_users(session_maker)


async def test_upsert_replaces_the_previous_key_for_the_same_provider(
    session_maker: async_sessionmaker[AsyncSession],
    seeded_users: None,
) -> None:
    encryption_key = generate_encryption_key()

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.provider_credentials.upsert(
            user_id=_OWNER,
            provider="openai",
            ciphertext=encrypt_api_key("sk-first-key-1111", key=encryption_key),
            key_hint=derive_key_hint("sk-first-key-1111"),
            verified_at=_NOW,
            now=_NOW,
        )

    later = datetime(2026, 8, 7, 9, 30, tzinfo=UTC)
    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.provider_credentials.upsert(
            user_id=_OWNER,
            provider="openai",
            ciphertext=encrypt_api_key("sk-second-key-2222", key=encryption_key),
            key_hint=derive_key_hint("sk-second-key-2222"),
            verified_at=later,
            now=later,
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        rows = await uow.provider_credentials.list_status(_OWNER)
        assert [row.provider for row in rows] == ["openai"]
        assert rows[0].key_hint == "2222"
        # The row is the same row: it kept when it was first connected.
        assert rows[0].created_at.astimezone(UTC) == _NOW
        assert rows[0].updated_at.astimezone(UTC) == later
        assert (
            await uow.provider_credentials.get_decrypted_api_key(
                _OWNER, "openai", encryption_key=encryption_key
            )
            == "sk-second-key-2222"
        )


async def test_one_user_holds_independent_keys_per_provider(
    session_maker: async_sessionmaker[AsyncSession],
    seeded_users: None,
) -> None:
    encryption_key = generate_encryption_key()

    async with PostgresUnitOfWork(session_maker) as uow:
        for provider, key in (("openai", "sk-oai-aaaa"), ("openrouter", "sk-or-bbbb")):
            await uow.provider_credentials.upsert(
                user_id=_OWNER,
                provider=provider,
                ciphertext=encrypt_api_key(key, key=encryption_key),
                key_hint=derive_key_hint(key),
                verified_at=_NOW,
                now=_NOW,
            )

    async with PostgresUnitOfWork(session_maker) as uow:
        rows = await uow.provider_credentials.list_status(_OWNER)
        assert [(row.provider, row.key_hint) for row in rows] == [
            ("openai", "aaaa"),
            ("openrouter", "bbbb"),
        ]


async def test_reads_are_scoped_to_the_owning_user(
    session_maker: async_sessionmaker[AsyncSession],
    seeded_users: None,
) -> None:
    encryption_key = generate_encryption_key()

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.provider_credentials.upsert(
            user_id=_OWNER,
            provider="openai",
            ciphertext=encrypt_api_key("sk-owner-only-cccc", key=encryption_key),
            key_hint="cccc",
            verified_at=_NOW,
            now=_NOW,
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        assert await uow.provider_credentials.list_status(_OTHER) == []
        assert await uow.provider_credentials.get(_OTHER, "openai") is None
        assert (
            await uow.provider_credentials.get_decrypted_api_key(
                _OTHER, "openai", encryption_key=encryption_key
            )
            is None
        )


async def test_delete_reports_whether_anything_was_disconnected(
    session_maker: async_sessionmaker[AsyncSession],
    seeded_users: None,
) -> None:
    encryption_key = generate_encryption_key()

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.provider_credentials.upsert(
            user_id=_OWNER,
            provider="ollama-cloud",
            ciphertext=encrypt_api_key("sk-ollama-dddd", key=encryption_key),
            key_hint="dddd",
            verified_at=_NOW,
            now=_NOW,
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        assert await uow.provider_credentials.delete(_OWNER, "ollama-cloud") is True

    async with PostgresUnitOfWork(session_maker) as uow:
        assert await uow.provider_credentials.delete(_OWNER, "ollama-cloud") is False
        assert await uow.provider_credentials.get(_OWNER, "ollama-cloud") is None
        # Another user's delete must not reach across accounts either.
        assert await uow.provider_credentials.delete(_OTHER, "openai") is False


async def test_a_ciphertext_written_under_another_key_refuses_to_decrypt(
    session_maker: async_sessionmaker[AsyncSession],
    seeded_users: None,
) -> None:
    written_with = generate_encryption_key()

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.provider_credentials.upsert(
            user_id=_OWNER,
            provider="openrouter",
            ciphertext=encrypt_api_key("sk-rotated-eeee", key=written_with),
            key_hint="eeee",
            verified_at=_NOW,
            now=_NOW,
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        with pytest.raises(CredentialDecryptError):
            await uow.provider_credentials.get_decrypted_api_key(
                _OWNER, "openrouter", encryption_key=generate_encryption_key()
            )


async def test_deleting_the_account_removes_its_stored_keys(
    session_maker: async_sessionmaker[AsyncSession],
    seeded_users: None,
) -> None:
    encryption_key = generate_encryption_key()

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.provider_credentials.upsert(
            user_id=_OTHER,
            provider="openai",
            ciphertext=encrypt_api_key("sk-cascade-ffff", key=encryption_key),
            key_hint="ffff",
            verified_at=_NOW,
            now=_NOW,
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.session.execute(delete(AuthUserRow).where(AuthUserRow.user_id == _OTHER))

    async with PostgresUnitOfWork(session_maker) as uow:
        assert await uow.provider_credentials.get(_OTHER, "openai") is None
