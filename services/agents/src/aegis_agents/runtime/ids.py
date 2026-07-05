"""Runtime identifier helpers."""

from __future__ import annotations

import secrets

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_runtime_id(prefix: str) -> str:
    suffix = "".join(secrets.choice(_CROCKFORD) for _ in range(26))
    return f"{prefix}_{suffix}"


def new_agent_session_id() -> str:
    suffix = "".join(secrets.choice(_CROCKFORD).lower() for _ in range(24))
    return f"agent-session:ags_{suffix}"


def new_transition_id() -> str:
    return new_runtime_id("ast")
