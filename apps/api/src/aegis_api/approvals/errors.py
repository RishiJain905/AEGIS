"""Approval workflow domain errors."""

from __future__ import annotations

from typing import Any

from aegis_contracts.approvals import ApprovalErrorCode


class ApprovalWorkflowError(Exception):
    def __init__(
        self,
        *,
        code: ApprovalErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)
