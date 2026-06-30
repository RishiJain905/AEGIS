"""Structured validation diagnostics for scenario packages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aegis_scenario_sdk.errors import ScenarioErrorCode


class ValidationDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ScenarioErrorCode
    path: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    def format_line(self) -> str:
        location = f" at {self.path}" if self.path else ""
        return f"[{self.code.value}]{location}: {self.message}"


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    diagnostics: list[ValidationDiagnostic] = Field(default_factory=list)
    package_checksum: str | None = None

    def raise_if_invalid(self) -> None:
        if not self.valid:
            lines = "\n".join(d.format_line() for d in self.diagnostics)
            raise ValueError(f"Scenario validation failed:\n{lines}")
