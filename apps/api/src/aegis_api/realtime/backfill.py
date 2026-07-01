"""PostgreSQL backfill republication endpoint."""

from __future__ import annotations

from aegis_contracts import BackfillRequestV1, BackfillResultV1
from aegis_contracts.versioning import BACKFILL_REQUEST_SCHEMA_VERSION
from aegis_event_streaming.backfill import PostgresBackfillService
from aegis_event_streaming.redis_client import create_redis_client
from fastapi import APIRouter, Request

from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


@router.post("/backfill", response_model=BackfillResultV1)
async def trigger_backfill(
    request: Request,
    body: BackfillRequestV1 | None = None,
) -> BackfillResultV1:
    settings = request.app.state.settings
    session_maker = get_db_session_maker()
    redis = create_redis_client(settings)
    try:
        service = PostgresBackfillService(session_maker, redis)
        req = body or BackfillRequestV1(schema_version=BACKFILL_REQUEST_SCHEMA_VERSION)
        return await service.backfill(req)
    finally:
        await redis.aclose()
