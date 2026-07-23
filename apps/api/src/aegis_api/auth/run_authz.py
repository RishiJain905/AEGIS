"""Shared owner-or-admin authorization for run-scoped routes.

Ownership is anchored to a run's ``ownerUserId`` (see ADR 0034 / AEGIS-OITB-008):

* Admins (``admin:manage``) may access any run.
* A non-admin may access only runs they own.
* Legacy rows with a ``None`` owner are treated as admin-only (fail-closed).
* An unknown run is a 404 (never leaking existence to non-owners); a known run
  the caller may not access is a 403.

The runs router keeps its own ``JSONResponse``-returning wrapper for backward
compatibility with its response envelope; every other run-scoped router uses
:func:`enforce_run_access` / :func:`require_run_access`, which raise
``HTTPException`` and integrate with FastAPI's standard error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aegis_contracts import AuthenticatedActorV1, PermissionV1, RunV1
from aegis_policy.authz.matrix import actor_has_permission
from fastapi import HTTPException

if TYPE_CHECKING:
    from aegis_persistence.unit_of_work import PostgresUnitOfWork


def actor_is_admin(actor: AuthenticatedActorV1) -> bool:
    """True when the actor holds the platform-wide ``admin:manage`` permission."""
    return actor_has_permission(actor, PermissionV1.ADMIN_MANAGE)


def has_run_access(run: RunV1, actor: AuthenticatedActorV1) -> bool:
    """Owner-or-admin decision for a resolved run.

    Admins always pass. A non-admin passes only when the run has an owner and it
    matches the actor; a ``None`` owner is admin-only.
    """
    if actor_is_admin(actor):
        return True
    return run.owner_user_id is not None and run.owner_user_id == actor.user_id


def enforce_run_access(
    run: RunV1 | None, actor: AuthenticatedActorV1, run_id: str
) -> RunV1:
    """Return ``run`` when the actor may access it, else raise ``HTTPException``.

    Raises 404 when ``run`` is ``None`` (unknown run) and 403 when the actor is
    neither the owner nor an admin. Mirrors the runs router semantics.
    """
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    if not has_run_access(run, actor):
        raise HTTPException(
            status_code=403, detail=f"Not authorized to access run: {run_id}"
        )
    return run


async def require_run_access(
    uow: PostgresUnitOfWork, run_id: str, actor: AuthenticatedActorV1
) -> RunV1:
    """Resolve ``run_id`` via ``uow`` and enforce owner-or-admin access."""
    run = await uow.runs.get_by_id(run_id)
    return enforce_run_access(run, actor, run_id)
