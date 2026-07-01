#!/usr/bin/env python3
"""Publish all pending outbox rows once (demo/validation helper)."""

from __future__ import annotations

import asyncio
import json

from aegis_contracts import load_settings
from aegis_event_streaming.redis_client import create_redis_client
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker


async def main() -> None:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    redis = create_redis_client(settings)
    try:
        relay = PostgresOutboxRelay(session_maker, redis)
        published = await relay.publish_until_empty()
        print(json.dumps({"published": published}))
    finally:
        await redis.aclose()
        await dispose_engine(engine)


if __name__ == "__main__":
    asyncio.run(main())
