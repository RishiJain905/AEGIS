"""Platform version compatibility checks."""

from __future__ import annotations

from aegis_contracts.versioning import WORKSPACE_VERSION
from packaging.version import InvalidVersion, Version


def is_platform_version_compatible(required: str, platform: str = WORKSPACE_VERSION) -> bool:
    """Return True when the platform version satisfies the scenario requirement."""
    try:
        required_version = Version(required)
        platform_version = Version(platform)
    except InvalidVersion:
        return required == platform
    return platform_version >= required_version
