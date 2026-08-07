"""Symmetric encryption for the API keys AEGIS holds on an operator's behalf.

These keys belong to the operator, not to us: they buy tokens on their subscription
and, at OpenRouter and OpenAI, can read their billing. So the store has to fail closed
— a ciphertext that has been altered, or one presented with the wrong key, must raise
rather than return anything the caller could mistake for a usable key.
"""

from __future__ import annotations

import pytest
from aegis_persistence.credentials import (
    CREDENTIAL_ENCRYPTION_ALGORITHM,
    CredentialDecryptError,
    CredentialKeyError,
    decrypt_api_key,
    derive_key_hint,
    encrypt_api_key,
    generate_encryption_key,
)

_API_KEY = "sk-proj-000000000000000000000abcd"


def test_round_trip_returns_the_original_key() -> None:
    key = generate_encryption_key()

    ciphertext = encrypt_api_key(_API_KEY, key=key)

    assert isinstance(ciphertext, bytes)
    assert _API_KEY.encode("utf-8") not in ciphertext
    assert decrypt_api_key(ciphertext, key=key) == _API_KEY


def test_encrypting_twice_produces_different_ciphertext() -> None:
    # Fernet carries a random IV; identical keys must not be correlatable by ciphertext.
    key = generate_encryption_key()

    assert encrypt_api_key(_API_KEY, key=key) != encrypt_api_key(_API_KEY, key=key)


def test_tampered_ciphertext_is_rejected() -> None:
    key = generate_encryption_key()
    ciphertext = bytearray(encrypt_api_key(_API_KEY, key=key))
    ciphertext[-1] ^= 0x01

    with pytest.raises(CredentialDecryptError):
        decrypt_api_key(bytes(ciphertext), key=key)


def test_a_different_encryption_key_cannot_read_the_ciphertext() -> None:
    ciphertext = encrypt_api_key(_API_KEY, key=generate_encryption_key())

    with pytest.raises(CredentialDecryptError):
        decrypt_api_key(ciphertext, key=generate_encryption_key())


def test_malformed_encryption_key_fails_loudly_on_both_paths() -> None:
    # A deployment that sets AEGIS_CREDENTIAL_ENCRYPTION_KEY to something that is not a
    # Fernet key must be told so, not silently degraded.
    with pytest.raises(CredentialKeyError):
        encrypt_api_key(_API_KEY, key="not-a-fernet-key")

    with pytest.raises(CredentialKeyError):
        decrypt_api_key(b"whatever", key="not-a-fernet-key")


def test_blank_api_keys_are_refused() -> None:
    key = generate_encryption_key()

    with pytest.raises(ValueError):
        encrypt_api_key("   ", key=key)


def test_key_hint_is_the_last_four_characters() -> None:
    assert derive_key_hint(_API_KEY) == "abcd"


def test_key_hint_never_exceeds_four_characters_for_short_keys() -> None:
    # Whatever the operator pasted, the hint is a hint — it may never become the key.
    assert derive_key_hint("ab") == "ab"
    assert len(derive_key_hint("x" * 200)) == 4


def test_algorithm_label_is_recorded_for_future_rotation() -> None:
    assert CREDENTIAL_ENCRYPTION_ALGORITHM == "fernet"
