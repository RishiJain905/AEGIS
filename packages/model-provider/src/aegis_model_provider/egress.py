"""Exact-destination egress policy for network-capable model adapters."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit, urlunsplit

from aegis_contracts.generation import ProviderErrorCode

from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error


def _normalized_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        msg = "Provider base URL must be an HTTP(S) URL without credentials, query, or fragment"
        raise ValueError(msg)

    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    path = parsed.path.rstrip("/") or ""
    return urlunsplit(SplitResult(parsed.scheme.lower(), netloc, path, "", ""))


def assert_provider_destination_allowed(
    *,
    base_url: str,
    allowed_base_urls: list[str],
    provider_id: str,
) -> str:
    """Return the normalized URL or fail closed without disclosing it in errors."""

    try:
        destination = _normalized_base_url(base_url)
        allowed = {_normalized_base_url(item) for item in allowed_base_urls if item.strip()}
    except (ValueError, UnicodeError) as exc:
        raise ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.VALIDATION_FAILED,
                message="Provider destination configuration is invalid",
                details={"providerId": provider_id},
            )
        ) from exc
    if not allowed or destination not in allowed:
        raise ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.VALIDATION_FAILED,
                message="Provider destination is not allowlisted",
                details={"providerId": provider_id},
            )
        )
    return destination
