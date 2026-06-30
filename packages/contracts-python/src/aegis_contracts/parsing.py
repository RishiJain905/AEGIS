"""Helpers for parsing contracts with structured errors."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from aegis_contracts.errors import ContractErrorCode, ContractValidationError


def parse_contract[T: BaseModel](model: type[T], data: object) -> T:
    try:
        return model.model_validate(data)
    except ContractValidationError:
        raise
    except ValidationError as exc:
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Contract validation failed",
            details={"errors": exc.errors()},
        ) from exc
