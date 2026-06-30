"""Canonical identifiers, timestamps, and ordering primitives."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, PlainSerializer

from aegis_contracts.errors import ContractErrorCode, ContractValidationError

AUTHORED_ID_PATTERN = re.compile(
    r"^(asset|incident|alert|evidence|agent-session|business-unit|edge|scenario|"
    r"scenario-version|relationship|service|user|device|identity|database|control):"
    r"[a-z0-9][a-z0-9._-]{0,126}$"
)
RUNTIME_ID_PATTERN = re.compile(
    r"^(evt|run|trc|inc|alt|evd|ags|prp|apr|act|mdl|scr|hyp)_[0-9A-HJKMNP-TV-Z]{26}$"
)

Sequence = Annotated[int, Field(ge=0)]
Revision = Annotated[int, Field(ge=0)]


def _validate_authored_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(
            code=ContractErrorCode.INVALID_IDENTIFIER,
            message="Authored identifier must be a string",
            details={"value": value},
        )
    if not AUTHORED_ID_PATTERN.fullmatch(value):
        raise ContractValidationError(
            code=ContractErrorCode.INVALID_IDENTIFIER,
            message=f"Invalid authored identifier: {value}",
            details={"value": value},
        )
    return value


def _validate_runtime_id(prefix: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(
            code=ContractErrorCode.INVALID_IDENTIFIER,
            message="Runtime identifier must be a string",
            details={"value": value},
        )
    if not RUNTIME_ID_PATTERN.fullmatch(value):
        raise ContractValidationError(
            code=ContractErrorCode.INVALID_IDENTIFIER,
            message=f"Invalid runtime identifier: {value}",
            details={"value": value, "expectedPrefix": prefix},
        )
    if not value.startswith(f"{prefix}_"):
        raise ContractValidationError(
            code=ContractErrorCode.INVALID_IDENTIFIER,
            message=f"Runtime identifier must use prefix {prefix}_",
            details={"value": value, "expectedPrefix": prefix},
        )
    return value


def _make_runtime_id_validator(prefix: str) -> Callable[[Any], str]:
    def validator(value: Any) -> str:
        return _validate_runtime_id(prefix, value)

    return validator


def _validate_utc_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=f"Invalid UTC timestamp: {value}",
                details={"value": value},
            ) from exc
    else:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Timestamp must be an ISO-8601 string or datetime",
            details={"value": value},
        )

    if parsed.tzinfo is None:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Timestamp must be timezone-aware (UTC)",
            details={"value": value},
        )

    return parsed.astimezone(UTC)


def _serialize_utc_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def validate_authored_id(value: Any) -> str:
    return _validate_authored_id(value)


def validate_runtime_id(prefix: str, value: Any) -> str:
    return _validate_runtime_id(prefix, value)


AuthoredId = Annotated[str, BeforeValidator(_validate_authored_id)]
AssetId = AuthoredId
IncidentId = Annotated[str, BeforeValidator(_validate_authored_id)]
AlertId = Annotated[str, BeforeValidator(_validate_authored_id)]
EvidenceId = Annotated[str, BeforeValidator(_validate_authored_id)]
AgentSessionId = Annotated[str, BeforeValidator(_validate_authored_id)]
ScenarioId = Annotated[str, BeforeValidator(_validate_authored_id)]
RelationshipId = AuthoredId
ClusterId = AuthoredId
EdgeId = AuthoredId

EventId = Annotated[str, BeforeValidator(_make_runtime_id_validator("evt"))]
RunId = Annotated[str, BeforeValidator(_make_runtime_id_validator("run"))]
TraceId = Annotated[str, BeforeValidator(_make_runtime_id_validator("trc"))]
CausationId = Annotated[str, BeforeValidator(_make_runtime_id_validator("evt"))]
CorrelationId = Annotated[str, BeforeValidator(_make_runtime_id_validator("trc"))]
ProposalId = Annotated[str, BeforeValidator(_make_runtime_id_validator("prp"))]
ApprovalId = Annotated[str, BeforeValidator(_make_runtime_id_validator("apr"))]
ActionId = Annotated[str, BeforeValidator(_make_runtime_id_validator("act"))]
ModelId = Annotated[str, BeforeValidator(_make_runtime_id_validator("mdl"))]
HypothesisId = Annotated[str, BeforeValidator(_make_runtime_id_validator("hyp"))]

UtcTimestamp = Annotated[
    datetime,
    BeforeValidator(_validate_utc_timestamp),
    PlainSerializer(_serialize_utc_timestamp, return_type=str),
]
SimTimestamp = UtcTimestamp
