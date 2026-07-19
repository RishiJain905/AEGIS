from __future__ import annotations

import json

from aegis_api.runs.router import _simulation_error_response
from aegis_simulation_domain.errors import SimulationError, SimulationErrorCode


def test_simulation_error_without_details_returns_structured_error() -> None:
    response = _simulation_error_response(
        SimulationError(
            code=SimulationErrorCode.VALIDATION_FAILED,
            message="invalid scenario",
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "schemaVersion": 1,
        "code": "VALIDATION_FAILED",
        "message": "invalid scenario",
        "details": {},
        "traceId": None,
    }
