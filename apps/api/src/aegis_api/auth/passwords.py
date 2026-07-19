"""Password hashing and policy for real username/password authentication.

Passwords are hashed with Argon2id (memory-hard, salted per hash by the library)
via :mod:`argon2`. Plaintext passwords are never stored, logged, or returned; only
the opaque encoded hash string (which embeds algorithm, parameters, and a random
per-password salt) is persisted. Verification is delegated to the library's
constant-time comparison, and unknown-user logins run a dummy verification so the
response time does not reveal whether a username exists (anti-enumeration).
"""

from __future__ import annotations

import contextlib

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Argon2id parameters. Defaults from argon2-cffi are OWASP-aligned; pinned here so
# a library default change cannot silently weaken stored hashes.
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

# A precomputed hash of a random throwaway secret. verify_password() runs against
# this when the account does not exist so unknown-username and wrong-password paths
# take comparable time and neither reveals account existence via timing.
_DUMMY_HASH = _HASHER.hash("aegis-nonexistent-account-timing-equalizer")

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64

PASSWORD_ALGORITHM = "argon2id"


def hash_password(password: str) -> str:
    """Return the Argon2id encoded hash for ``password``.

    The returned string is safe to persist; it contains the algorithm, parameters,
    and a random salt but not the plaintext.
    """
    return _HASHER.hash(password)


def verify_password(*, password: str, password_hash: str | None) -> bool:
    """Constant-time-ish verification of ``password`` against ``password_hash``.

    When ``password_hash`` is ``None`` (no such account / no credential) a dummy
    verification is still performed so callers cannot distinguish "unknown user"
    from "wrong password" by timing. Always returns ``False`` in that case.
    """
    if not password_hash:
        with contextlib.suppress(VerifyMismatchError, VerificationError, InvalidHashError):
            _HASHER.verify(_DUMMY_HASH, password)
        return False
    try:
        _HASHER.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_policy(password: str) -> None:
    """Raise :class:`ContractValidationError` if the password is too weak.

    Enforced server-side; the UI hint is advisory only. Kept deliberately simple
    (length floor plus a basic character-class requirement) so it fails closed and
    is easy to reason about, without leaking specifics that aid targeted guessing.
    """
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message=f"Password must be at least {PASSWORD_MIN_LENGTH} characters",
            details={"minLength": PASSWORD_MIN_LENGTH},
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message=f"Password must be at most {PASSWORD_MAX_LENGTH} characters",
            details={"maxLength": PASSWORD_MAX_LENGTH},
        )
    has_letter = any(char.isalpha() for char in password)
    has_non_letter = any(not char.isalpha() for char in password)
    if not (has_letter and has_non_letter):
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Password must include at least one letter and one non-letter character",
            details={},
        )


def normalize_username(username: str) -> str:
    """Validate and normalize a username (case-insensitive, trimmed)."""
    candidate = (username or "").strip().lower()
    if not (USERNAME_MIN_LENGTH <= len(candidate) <= USERNAME_MAX_LENGTH):
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message=(
                f"Username must be between {USERNAME_MIN_LENGTH} and "
                f"{USERNAME_MAX_LENGTH} characters"
            ),
            details={},
        )
    if not all(char.isalnum() or char in {".", "_", "-"} for char in candidate):
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Username may only contain letters, digits, '.', '_' and '-'",
            details={},
        )
    return candidate
