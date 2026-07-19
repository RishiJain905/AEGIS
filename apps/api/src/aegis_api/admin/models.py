"""Response shapes for the admin console API.

These are read-only aggregation views specific to the administration surface (users
directory, enforced-policy snapshot, non-secret platform settings). Following the
precedent of the providers and observability routers, admin dashboard responses are
local API models rather than shared domain contracts: they carry no persisted event
or cross-service payload, only projections of state that already lives in the auth
registry, the policy package, and runtime settings.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ADMIN_SCHEMA_VERSION = 1


class _AdminModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AdminUserV1(_AdminModel):
    user_id: str
    display_name: str
    status: str
    roles: list[str]
    permissions: list[str]


class AdminCreateUserRequestV1(_AdminModel):
    """Admin-only request to provision a credentialed account with roles."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(default="", max_length=256)
    roles: list[str] = Field(min_length=1)


class AdminUsersResponseV1(_AdminModel):
    schema_version: int = ADMIN_SCHEMA_VERSION
    users: list[AdminUserV1]
    total: int


class AdminRolePermissionsV1(_AdminModel):
    role: str
    permissions: list[str]


class AdminActionClassV1(_AdminModel):
    action_class: str
    label: str
    approval_required: bool
    description: str


class AdminCommandV1(_AdminModel):
    command: str
    action_class: str
    scenario_restricted: bool


class AdminPolicyResponseV1(_AdminModel):
    schema_version: int = ADMIN_SCHEMA_VERSION
    roles: list[AdminRolePermissionsV1]
    permissions: list[str]
    action_classes: list[AdminActionClassV1]
    commands: list[AdminCommandV1]
    approver_roles: list[str]


class AdminSettingsResponseV1(_AdminModel):
    schema_version: int = ADMIN_SCHEMA_VERSION
    environment: str
    version: str
    log_level: str
    provider: dict[str, object]
    websocket: dict[str, object]
    security: dict[str, object]
    observability: dict[str, object]
    auth: dict[str, object]
    health: dict[str, object]
