"""Operator console + ops-feed read services.

These give the player the same read/analysis surface the agents work from — event search
and asset deep-dive — plus a unified ops feed, all as thin projections over the events
table (no new storage). The operator and the agents work the same evidence pool as peers.
Ownership is enforced by the router before any of this runs.
"""

from __future__ import annotations

from typing import Any

from aegis_contracts import (
    ConsoleAssetDetailV1,
    ConsoleAssetRelationshipV1,
    ConsoleEventSearchRequestV1,
    ConsoleEventSearchResultV1,
    ConsoleEventV1,
    RunFeedEntryV1,
    RunFeedPageV1,
)
from aegis_contracts.event_query import event_asset_id, event_matches_filters
from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.versioning import (
    CONSOLE_ASSET_DETAIL_SCHEMA_VERSION,
    CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
    CONSOLE_EVENT_SEARCH_RESULT_SCHEMA_VERSION,
    RUN_FEED_ENTRY_SCHEMA_VERSION,
    RUN_FEED_PAGE_SCHEMA_VERSION,
)
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork

# Recent-event window included in an asset deep-dive.
_ASSET_RECENT_EVENTS = 25

# Bounded window scanned per search/feed page before in-Python filtering; keeps a single
# query cheap while cursor pagination walks the full stream across pages.
_SCAN_WINDOW = 2000

# Maps event-type prefixes to a coarse feed category the UI can group/collapse on.
_FEED_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("agent.", "agent"),
    ("operator.action", "operator_action"),
    ("run.roe", "roe"),
    ("proposal.", "proposal"),
    ("policy.", "policy"),
    ("approval.", "approval"),
    ("action.executed", "execution"),
    ("incident.", "incident"),
    ("detection.alert", "alert"),
    ("alert.", "alert"),
    # A hidden condition becoming visible is the run's loudest beat, and it never reached
    # the feed: the bare "reveal" prefix below matches no event type the simulation emits.
    ("sim.hidden_condition.", "reveal"),
    ("reveal", "reveal"),
    ("directive.", "directive"),
)

# Event types surfaced in the ops feed (the operator's live heartbeat). Anything not
# matching a feed category is a low-level sim/telemetry event and is excluded.
_FEED_TYPE_PREFIXES: tuple[str, ...] = tuple(prefix for prefix, _ in _FEED_CATEGORIES)


def _feed_category(event_type: str) -> str | None:
    for prefix, category in _FEED_CATEGORIES:
        if event_type.startswith(prefix):
            return category
    return None


class ConsoleService:
    async def search_events(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        request: ConsoleEventSearchRequestV1,
    ) -> ConsoleEventSearchResultV1:
        repo = PostgresEventQueryRepository(uow.session)
        from_sequence = request.cursor
        events = await repo.list_by_run(
            run_id, from_sequence=from_sequence, limit=_SCAN_WINDOW
        )
        matched: list[ConsoleEventV1] = []
        last_sequence: int | None = None
        for event in events:
            last_sequence = event.sequence
            if not self._matches(event, request):
                continue
            matched.append(
                ConsoleEventV1(
                    event_id=event.event_id,
                    sequence=event.sequence,
                    type=event.type,
                    sim_time=event.sim_time.isoformat(),
                    asset_id=event_asset_id(event),
                    payload=event.payload,
                )
            )
            if len(matched) >= request.limit:
                break
        next_cursor = (
            (matched[-1].sequence + 1)
            if len(matched) >= request.limit and last_sequence is not None
            else None
        )
        return ConsoleEventSearchResultV1(
            schema_version=CONSOLE_EVENT_SEARCH_RESULT_SCHEMA_VERSION,
            events=matched,
            count=len(matched),
            next_cursor=next_cursor,
        )

    async def asset_detail(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        asset_id: str,
    ) -> ConsoleAssetDetailV1 | None:
        """Asset deep-dive from the latest operator-facing graph snapshot + recent events.

        Returns None when the run has no snapshot or the asset is absent, so the router can
        404. Reads the same fog-of-war-filtered snapshot the graph API serves — no new leak.
        """
        snapshot = await PostgresGraphSnapshotRepository(uow.session).get_latest_for_run(
            run_id
        )
        if snapshot is None:
            return None
        node = next((n for n in snapshot.nodes if n.id == asset_id), None)
        if node is None:
            return None

        relationships: list[ConsoleAssetRelationshipV1] = []
        for edge in snapshot.edges:
            if edge.source == asset_id:
                direction = "outbound"
            elif edge.target == asset_id:
                direction = "inbound"
            else:
                continue
            relationships.append(
                ConsoleAssetRelationshipV1(
                    edge_id=edge.id,
                    relationship_type=edge.relationship_type.value,
                    source_asset_id=edge.source,
                    target_asset_id=edge.target,
                    direction=direction,
                )
            )

        recent = await self.search_events(
            uow,
            run_id=run_id,
            request=ConsoleEventSearchRequestV1(
                schema_version=CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
                asset_id=asset_id,
                limit=_ASSET_RECENT_EVENTS,
            ),
        )
        return ConsoleAssetDetailV1(
            schema_version=CONSOLE_ASSET_DETAIL_SCHEMA_VERSION,
            asset_id=node.id,
            entity_type=node.entity_type.value,
            asset_type=node.asset_type.value,
            label=node.label,
            status=node.status.value,
            risk_score=node.risk_score,
            criticality=node.criticality,
            cluster_id=node.cluster_id,
            relationships=relationships,
            recent_events=recent.events,
        )

    def _matches(
        self,
        event: DomainEventEnvelopeV1,
        request: ConsoleEventSearchRequestV1,
    ) -> bool:
        # One matcher for both surfaces: the agents' search_events tool runs the
        # same filters, so a query the Evidence tab answers is a query the
        # copilot can answer too — and a cited event id is searchable here.
        return event_matches_filters(
            event,
            asset_id=request.asset_id,
            event_type_prefix=request.event_type_prefix,
            text=request.text,
            from_sim_time=request.from_sim_time,
            to_sim_time=request.to_sim_time,
        )

    async def feed(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        cursor: int | None,
        limit: int,
    ) -> RunFeedPageV1:
        repo = PostgresEventQueryRepository(uow.session)
        events = await repo.list_by_run(run_id, from_sequence=cursor, limit=_SCAN_WINDOW)
        entries: list[RunFeedEntryV1] = []
        for event in events:
            category = _feed_category(event.type)
            if category is None:
                continue
            entries.append(
                RunFeedEntryV1(
                    schema_version=RUN_FEED_ENTRY_SCHEMA_VERSION,
                    sequence=event.sequence,
                    event_id=event.event_id,
                    type=event.type,
                    category=category,
                    sim_time=event.sim_time.isoformat(),
                    initiator=_feed_initiator(event.payload),
                    summary=_feed_summary(event),
                    payload=event.payload,
                )
            )
            if len(entries) >= limit:
                break
        next_cursor = (entries[-1].sequence + 1) if len(entries) >= limit else None
        return RunFeedPageV1(
            schema_version=RUN_FEED_PAGE_SCHEMA_VERSION,
            entries=entries,
            next_cursor=next_cursor,
        )


def _feed_initiator(payload: dict[str, Any]) -> str | None:
    value = payload.get("initiator")
    return value if isinstance(value, str) else None


def _feed_summary(event: DomainEventEnvelopeV1) -> str:
    asset = event_asset_id(event)
    if asset:
        return f"{event.type} ({asset})"
    return event.type
