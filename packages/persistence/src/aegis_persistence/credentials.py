"""Encryption for third-party API keys held on an operator's behalf.

A run can be driven by the operator's own model subscription, which means AEGIS keeps
their provider API key. That key is theirs — it spends their money and, at some
providers, reads their billing — so it is stored encrypted at rest and only ever
decrypted into memory for the moment a provider client is built.

Fernet (AES-128-CBC with an HMAC, from ``cryptography``) is the whole mechanism: one
symmetric key for the deployment, supplied as ``AEGIS_CREDENTIAL_ENCRYPTION_KEY``,
authenticating every ciphertext it produces. Authentication is the point — a row an
attacker edited in the database cannot be made to decrypt into a key of their choosing;
it raises instead. ``algorithm`` is recorded beside each row so a future scheme can be
introduced without guessing how existing rows were written.

The one plaintext derivative that persists is the key hint: the last four characters,
so the console can say *Connected (…abcd)* without the server disclosing the key.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

__all__ = [
    "CREDENTIAL_ENCRYPTION_ALGORITHM",
    "KEY_HINT_LENGTH",
    "CredentialCryptoError",
    "CredentialDecryptError",
    "CredentialKeyError",
    "decrypt_api_key",
    "derive_key_hint",
    "encrypt_api_key",
    "generate_encryption_key",
]

#: Recorded on every row so a later scheme can be told apart from this one.
CREDENTIAL_ENCRYPTION_ALGORITHM = "fernet"

#: How much of the key the console is allowed to see. Four characters identifies which
#: key is connected without narrowing the search space for the rest of it.
KEY_HINT_LENGTH = 4


class CredentialCryptoError(Exception):
    """Base for every failure to encrypt or decrypt a stored provider key."""


class CredentialKeyError(CredentialCryptoError):
    """The deployment's encryption key is missing or is not a usable Fernet key."""


class CredentialDecryptError(CredentialCryptoError):
    """A stored ciphertext could not be read: it was altered, or written under another key."""


def generate_encryption_key() -> str:
    """A fresh deployment encryption key, in the form ``AEGIS_CREDENTIAL_ENCRYPTION_KEY`` takes."""
    return Fernet.generate_key().decode("ascii")


def _cipher(key: str) -> Fernet:
    try:
        return Fernet(key.encode("ascii"))
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        # Deliberately says nothing about the key's content: this message reaches logs.
        msg = "AEGIS_CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key"
        raise CredentialKeyError(msg) from exc


def encrypt_api_key(plaintext: str, *, key: str) -> bytes:
    """Encrypt one provider API key for storage.

    Raises ``CredentialKeyError`` if the deployment key is unusable, and ``ValueError``
    for a blank API key — a stored empty credential would look connected and fail at
    generation time, which is the worst of both.
    """
    if not plaintext.strip():
        msg = "API key must not be blank"
        raise ValueError(msg)
    return _cipher(key).encrypt(plaintext.encode("utf-8"))


def decrypt_api_key(ciphertext: bytes, *, key: str) -> str:
    """Recover a stored provider API key, or raise.

    There is no lenient path here on purpose. A caller that cannot decrypt must ask the
    operator to reconnect, never fall back to an environment key or an empty string.
    """
    try:
        plaintext = _cipher(key).decrypt(ciphertext)
    except InvalidToken as exc:
        msg = "Stored provider credential could not be decrypted"
        raise CredentialDecryptError(msg) from exc
    return plaintext.decode("utf-8")


def derive_key_hint(plaintext: str) -> str:
    """The last few characters of a key, for display only."""
    return plaintext[-KEY_HINT_LENGTH:]
