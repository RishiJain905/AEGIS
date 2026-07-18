"""Sanitize provider payloads before persistence or logging."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|cookie|set-cookie|"
    r"session|refresh[_-]?token|access[_-]?token|private[_-]?key|credential|"
    r"csrf|bearer)",
    re.IGNORECASE,
)

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-+=/]+", re.IGNORECASE),
    re.compile(
        r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._\-+=/]+",
        re.IGNORECASE,
    ),
    re.compile(r"(?i)(password|passwd|secret)\s*[:=]\s*\S+"),
)

SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "proxy-authorization",
    }
)


def redact_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def _is_sensitive_key(key: str) -> bool:
    return bool(SENSITIVE_KEY_PATTERN.search(key))


def redact_value(value: Any, *, parent_key: str | None = None) -> Any:
    if parent_key is not None and _is_sensitive_key(parent_key):
        return REDACTED
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, dict):
        return redact_mapping(value)
    return value


def redact_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(item, parent_key=key) for key, item in payload.items()}


def redact_headers(headers: dict[str, str] | list[tuple[str, str]]) -> dict[str, str]:
    items = headers if isinstance(headers, list) else list(headers.items())
    result: dict[str, str] = {}
    for key, value in items:
        if key.lower() in SENSITIVE_HEADER_NAMES or _is_sensitive_key(key):
            result[key] = REDACTED
        else:
            result[key] = redact_string(value)
    return result


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


def contains_sensitive_material(value: str) -> bool:
    return contains_secret_material(value)
