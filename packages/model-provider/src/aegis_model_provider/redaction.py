"""Sanitize provider payloads before persistence or logging."""

from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._-]+", re.IGNORECASE),
)

REDACTED = "[REDACTED]"


def redact_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    return value


def sanitize_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized_any = redact_value(payload)
    if not isinstance(sanitized_any, dict):
        return payload
    sanitized: dict[str, Any] = sanitized_any
    messages = sanitized.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "system":
                message["content"] = REDACTED
    return sanitized


def contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)
