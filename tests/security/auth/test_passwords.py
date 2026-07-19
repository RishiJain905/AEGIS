"""Offline unit tests for password hashing, verification, and policy.

These run without PostgreSQL and cover the security-critical invariants: passwords
are stored only as an Argon2id hash (never plaintext), verification is constant-time
via the vetted library, unknown accounts still run a verification (anti-enumeration),
and the server-side policy fails closed on weak passwords.
"""

from __future__ import annotations

import time

import pytest
from aegis_api.auth.passwords import (
    PASSWORD_ALGORITHM,
    hash_password,
    normalize_username,
    validate_password_policy,
    verify_password,
)
from aegis_contracts.errors import ContractValidationError


def test_hash_is_not_plaintext_and_is_argon2id() -> None:
    password = "correct horse battery staple"
    hashed = hash_password(password)
    assert password not in hashed
    assert hashed.startswith("$argon2id$")
    assert PASSWORD_ALGORITHM == "argon2id"


def test_hash_is_salted_and_differs_per_call() -> None:
    password = "correct horse battery staple"
    assert hash_password(password) != hash_password(password)


def test_verify_accepts_correct_and_rejects_wrong() -> None:
    hashed = hash_password("s3cret-passphrase")
    assert verify_password(password="s3cret-passphrase", password_hash=hashed) is True
    assert verify_password(password="wrong-passphrase", password_hash=hashed) is False


def test_verify_with_no_hash_returns_false_but_still_runs() -> None:
    # Unknown account path: no stored hash. Must return False and still spend time
    # verifying against the dummy hash so it is indistinguishable from a wrong password.
    start = time.perf_counter()
    assert verify_password(password="anything", password_hash=None) is False
    dummy_elapsed = time.perf_counter() - start

    hashed = hash_password("some-real-password")
    start = time.perf_counter()
    verify_password(password="anything", password_hash=hashed)
    real_elapsed = time.perf_counter() - start

    # Both paths perform an Argon2id verification; the dummy path is not a trivial
    # early-return (which would leak account existence via timing).
    assert dummy_elapsed > real_elapsed * 0.2


@pytest.mark.parametrize(
    "weak",
    [
        "short1",  # too short
        "alllettersonly",  # no non-letter
        "1234567890123",  # no letter
    ],
)
def test_policy_rejects_weak_passwords(weak: str) -> None:
    with pytest.raises(ContractValidationError):
        validate_password_policy(weak)


def test_policy_accepts_strong_password() -> None:
    validate_password_policy("longenough-pass1")


def test_normalize_username_lowercases_and_trims() -> None:
    assert normalize_username("  Operator_One  ") == "operator_one"


@pytest.mark.parametrize("bad", ["ab", "has spaces", "bad!char", "x" * 65])
def test_normalize_username_rejects_invalid(bad: str) -> None:
    with pytest.raises(ContractValidationError):
        normalize_username(bad)
