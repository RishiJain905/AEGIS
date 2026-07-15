"""Opaque token helpers for sessions and WebSocket tickets."""

from __future__ import annotations

import hashlib
import secrets


def generate_opaque_token(*, nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_id() -> str:
    return f"sess_{secrets.token_hex(16)}"


def generate_csrf_token() -> str:
    return f"csrf_{secrets.token_urlsafe(24)}"


def generate_audit_event_id() -> str:
    return f"sae_{secrets.token_hex(16)}"


def constant_time_equals(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)
