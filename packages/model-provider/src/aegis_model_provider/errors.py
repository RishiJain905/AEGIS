"""Provider runtime errors normalized to canonical contracts."""

from __future__ import annotations

from aegis_contracts.generation import ProviderErrorCode, ProviderErrorV1
from aegis_contracts.versioning import PROVIDER_ERROR_SCHEMA_VERSION


class ProviderRuntimeError(Exception):
    def __init__(self, error: ProviderErrorV1) -> None:
        super().__init__(error.message)
        self.error = error


def make_provider_error(
    *,
    code: ProviderErrorCode,
    message: str,
    retryable: bool = False,
    details: dict[str, object] | None = None,
    trace_id: str | None = None,
) -> ProviderErrorV1:
    return ProviderErrorV1(
        schema_version=PROVIDER_ERROR_SCHEMA_VERSION,
        code=code,
        message=message,
        retryable=retryable,
        details=details or {},
        trace_id=trace_id,
    )


def raise_provider_error(
    *,
    code: ProviderErrorCode,
    message: str,
    retryable: bool = False,
    details: dict[str, object] | None = None,
    trace_id: str | None = None,
) -> None:
    raise ProviderRuntimeError(
        make_provider_error(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
            trace_id=trace_id,
        )
    )
