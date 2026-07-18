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
        if required == platform:
            return True
        if required.startswith("0.0.0-phase") and platform == WORKSPACE_VERSION:
            return True
        if required.startswith("0.0.0-phase") and platform.startswith("0.0.0-phase"):
            required_phase = int(required.removeprefix("0.0.0-phase"))
            platform_phase = int(platform.removeprefix("0.0.0-phase"))
            return platform_phase >= required_phase
        return False
    return platform_version >= required_version
