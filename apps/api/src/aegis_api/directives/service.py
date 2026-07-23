"""Standing-directive application service (Phase 7).

Create / list / delete persistent operator taskings. Directives are matched against new
alerts by the autonomy poller (:mod:`aegis_agents.autonomy`), so this service only owns the
lifecycle: it persists the row and emits the operator-attributed lifecycle events. Ownership
is enforced by the router before any method here runs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import CreateDirectiveRequestV1, StandingDirectiveV1
from aegis_contracts.versioning import STANDING_DIRECTIVE_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_api.directives.events import (
    build_directive_created_event,
    build_directive_deleted_event,
)


class DirectiveNotFoundError(Exception):
    """A directive id does not exist for the run."""


class DirectiveService:
    async def create(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        request: CreateDirectiveRequestV1,
        actor_id: str,
    ) -> StandingDirectiveV1:
        directive = StandingDirectiveV1(
            schema_version=STANDING_DIRECTIVE_SCHEMA_VERSION,
            id=new_runtime_id("dir"),
            run_id=run_id,
            text=request.text,
            scope_asset_ids=list(request.scope_asset_ids),
            scope_zone_ids=list(request.scope_zone_ids),
            active=True,
            created_by=actor_id,
            created_at=datetime.now(UTC),
        )
        await uow.directives.add(directive)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_directive_created_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                actor_id=actor_id,
                trace_id=new_runtime_id("trc"),
                directive_id=directive.id,
                text=directive.text,
                scope_asset_ids=directive.scope_asset_ids,
                scope_zone_ids=directive.scope_zone_ids,
            )
        )
        return directive

    async def list_for_run(
        self, uow: PostgresUnitOfWork, *, run_id: str
    ) -> list[StandingDirectiveV1]:
        return await uow.directives.list_for_run(run_id)

    async def delete(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        directive_id: str,
        actor_id: str,
    ) -> StandingDirectiveV1:
        existing = await uow.directives.get(directive_id)
        if existing is None or existing.run_id != run_id:
            raise DirectiveNotFoundError(directive_id)
        deactivated = await uow.directives.deactivate(directive_id)
        assert deactivated is not None  # get() above proved the row exists
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_directive_deleted_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                actor_id=actor_id,
                trace_id=new_runtime_id("trc"),
                directive_id=directive_id,
            )
        )
        return deactivated
