"""Secret-provider seam used by production startup validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


class SecretProvider(Protocol):
    """Minimal provider contract; implementations must not log returned values."""

    def get_secret(self, name: str) -> str | None:
        """Return a secret/config value by canonical environment name."""


@dataclass(frozen=True, slots=True)
class EnvironmentSecretProvider:
    """Resolve process environment first, with parsed settings as a fallback."""

    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    fallback: Mapping[str, object] = field(default_factory=dict)

    def get_secret(self, name: str) -> str | None:
        value: object | None = self.environ.get(name)
        if value is None:
            value = self.fallback.get(name)
        if value is None:
            return None
        return str(value)
