"""Untrusted scenario content safety validation."""

from __future__ import annotations

import re
from typing import Any

from aegis_scenario_sdk.diagnostics import ValidationDiagnostic
from aegis_scenario_sdk.errors import ScenarioErrorCode

FORBIDDEN_KEY_PATTERN = re.compile(
    r"(prompt|shell|python|script|exec|code)$",
    re.IGNORECASE,
)
UNSAFE_URL_PATTERN = re.compile(r"(https?|file|ftp)://", re.IGNORECASE)
SHELL_PATTERN = re.compile(r"(;|\||&&|`|\$\()")


def _scan_value(path: str, value: Any, diagnostics: list[ValidationDiagnostic]) -> None:
    if isinstance(value, dict):
        _scan_mapping(path, value, diagnostics)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_value(f"{path}[{index}]", item, diagnostics)
        return
    if not isinstance(value, str):
        return
    if UNSAFE_URL_PATTERN.search(value):
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.UNSAFE_CONTENT,
                path=path,
                message="Unrestricted URL values are not allowed in scenario content",
                details={"value": value},
            )
        )
    if SHELL_PATTERN.search(value):
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.UNSAFE_CONTENT,
                path=path,
                message="Shell-like command patterns are not allowed in scenario content",
                details={"value": value},
            )
        )


def _scan_mapping(
    path: str,
    mapping: dict[str, Any],
    diagnostics: list[ValidationDiagnostic],
) -> None:
    for key, value in mapping.items():
        key_path = f"{path}.{key}" if path else key
        if FORBIDDEN_KEY_PATTERN.search(key):
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.UNSAFE_CONTENT,
                    path=key_path,
                    message=f"Forbidden key name: {key}",
                )
            )
        _scan_value(key_path, value, diagnostics)


def validate_media_path(path: str, field_path: str) -> ValidationDiagnostic | None:
    if path.startswith("/") or ".." in path.split("/"):
        return ValidationDiagnostic(
            code=ScenarioErrorCode.UNSAFE_CONTENT,
            path=field_path,
            message="Media paths must be relative and must not traverse upward",
            details={"path": path},
        )
    if UNSAFE_URL_PATTERN.search(path):
        return ValidationDiagnostic(
            code=ScenarioErrorCode.UNSAFE_CONTENT,
            path=field_path,
            message="Media paths cannot use unrestricted URL schemes",
            details={"path": path},
        )
    return None


def scan_raw_document(raw: Any, path: str = "") -> list[ValidationDiagnostic]:
    diagnostics: list[ValidationDiagnostic] = []
    if isinstance(raw, dict):
        _scan_mapping(path, raw, diagnostics)
    else:
        _scan_value(path, raw, diagnostics)
    return diagnostics
