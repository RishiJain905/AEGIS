"""Canonical Redis stream and consumer group names."""

from __future__ import annotations

DOMAIN_EVENTS_STREAM = "aegis:stream:domain-events"
DOMAIN_EVENTS_DLQ_STREAM = "aegis:stream:domain-events:dlq"
DOMAIN_EVENTS_CONSUMER_GROUP = "aegis-domain-events"
DEFAULT_CHANNEL = "events"
