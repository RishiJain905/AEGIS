"""Deterministic runtime identifier generation."""

from __future__ import annotations

import hashlib

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford32(data: bytes, length: int = 26) -> str:
    value = int.from_bytes(data[:16], "big")
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(chars)


def derive_runtime_id(prefix: str, *, run_seed: int, sequence: int, kind: str) -> str:
    digest = hashlib.sha256(f"{run_seed}:{sequence}:{kind}".encode()).digest()
    return f"{prefix}_{_encode_crockford32(digest)}"


def derive_event_id(*, run_seed: int, sequence: int, event_type: str) -> str:
    return derive_runtime_id("evt", run_seed=run_seed, sequence=sequence, kind=event_type)


def derive_trace_id(*, run_seed: int, sequence: int) -> str:
    return derive_runtime_id("trc", run_seed=run_seed, sequence=sequence, kind="trace")


def derive_run_id(*, run_seed: int, scenario_version_id: str) -> str:
    return derive_runtime_id(
        "run",
        run_seed=run_seed,
        sequence=0,
        kind=scenario_version_id,
    )


def derive_checkpoint_id(*, run_seed: int, sequence: int) -> str:
    digest = hashlib.sha256(f"{run_seed}:{sequence}:checkpoint".encode()).digest()
    return f"ckp_{_encode_crockford32(digest, 20)}"
