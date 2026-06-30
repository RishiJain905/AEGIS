"""Deliberate import boundary violation fixture."""

from aegis_api.main import WORKSPACE_VERSION  # noqa: F401 — intentional violation

VIOLATION = WORKSPACE_VERSION
