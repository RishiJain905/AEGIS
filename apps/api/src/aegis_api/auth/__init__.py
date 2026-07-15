"""Phase 30 authentication and authorization API package."""

from aegis_api.auth.deps import (
    AuthDependencyError,
    CurrentActor,
    auth_error_response,
    optional_actor,
    require_actor,
    require_permission,
)
from aegis_api.auth.startup import assert_secure_auth_configuration, seed_dev_identities

__all__ = [
    "AuthDependencyError",
    "CurrentActor",
    "assert_secure_auth_configuration",
    "auth_error_response",
    "optional_actor",
    "require_actor",
    "require_permission",
    "seed_dev_identities",
]
