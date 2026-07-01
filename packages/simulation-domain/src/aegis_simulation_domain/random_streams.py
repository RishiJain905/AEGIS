"""Run-local seeded random streams."""

from __future__ import annotations

import hashlib
from random import Random


def _stream_seed(run_seed: int, stream_name: str) -> int:
    digest = hashlib.sha256(f"{run_seed}:{stream_name}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


class SeededRandomStreams:
    def __init__(self, run_seed: int) -> None:
        self._run_seed = run_seed
        self._streams: dict[str, Random] = {}

    def stream(self, name: str) -> Random:
        if name not in self._streams:
            self._streams[name] = Random(_stream_seed(self._run_seed, name))
        return self._streams[name]

    def to_snapshot(self) -> dict[str, list[int]]:
        return {name: list(rng.getstate()[1]) for name, rng in sorted(self._streams.items())}

    def restore_from_snapshot(self, snapshot: dict[str, list[int]]) -> None:
        self._streams.clear()
        for name in sorted(snapshot):
            rng = Random(_stream_seed(self._run_seed, name))
            version, _, gauss_next = rng.getstate()
            rng.setstate((version, tuple(snapshot[name]), gauss_next))
            self._streams[name] = rng
