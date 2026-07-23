"""Phase 7 standing-directive lifecycle (create / list / delete) integration tests."""

from __future__ import annotations

import os

import pytest
from aegis_api.directives.service import DirectiveNotFoundError, DirectiveService
from aegis_contracts import CreateDirectiveRequestV1, load_settings
from aegis_contracts.versioning import CREATE_DIRECTIVE_REQUEST_SCHEMA_VERSION
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)


def _session_maker():
    return get_session_maker(load_settings(), engine=create_engine(load_settings()))


def _request() -> CreateDirectiveRequestV1:
    return CreateDirectiveRequestV1(
        schema_version=CREATE_DIRECTIVE_REQUEST_SCHEMA_VERSION,
        text="Monitor the logistics zone network for lateral movement",
        scope_asset_ids=["asset:svc-api-gateway"],
        scope_zone_ids=[],
    )


@pytest.mark.asyncio
async def test_create_list_and_delete_directive() -> None:
    service = DirectiveService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        created = await service.create(
            uow, run_id=run_id, request=_request(), actor_id="user:op"
        )
        assert created.active is True
        assert created.run_id == run_id
        assert created.created_by == "user:op"

        listed = await service.list_for_run(uow, run_id=run_id)
        assert any(d.id == created.id for d in listed)
        active = await uow.directives.list_active_for_run(run_id)
        assert any(d.id == created.id for d in active)

        events = await uow.events.list_by_run(run_id)
        assert any(e.type == "directive.created" for e in events)

        deleted = await service.delete(
            uow, run_id=run_id, directive_id=created.id, actor_id="user:op"
        )
        assert deleted.active is False
        active_after = await uow.directives.list_active_for_run(run_id)
        assert all(d.id != created.id for d in active_after)
        events_after = await uow.events.list_by_run(run_id)
        assert any(e.type == "directive.deleted" for e in events_after)


@pytest.mark.asyncio
async def test_delete_unknown_directive_raises() -> None:
    service = DirectiveService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        with pytest.raises(DirectiveNotFoundError):
            await service.delete(
                uow, run_id=run_id, directive_id="dir_missing", actor_id="user:op"
            )
