"""Scenario SDK identifier primitives."""

from __future__ import annotations

import re
from typing import Annotated, Any

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from pydantic import BeforeValidator

SCENARIO_LOCAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")


def _validate_scenario_local_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Scenario-local identifier must be a string",
            details={"value": value},
        )
    if not SCENARIO_LOCAL_ID_PATTERN.fullmatch(value):
        raise ContractValidationError(
            code=ContractErrorCode.VALIDATION_FAILED,
            message=f"Invalid scenario-local identifier: {value}",
            details={"value": value},
        )
    return value


ScenarioLocalId = Annotated[str, BeforeValidator(_validate_scenario_local_id)]
