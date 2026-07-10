"""Runtime identifier helpers for scoring artifacts."""

from __future__ import annotations

import secrets

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_runtime_id(prefix: str) -> str:
    suffix = "".join(secrets.choice(_CROCKFORD) for _ in range(26))
    return f"{prefix}_{suffix}"
