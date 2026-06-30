"""AEGIS PostgreSQL persistence package."""

from aegis_persistence.errors import DuplicateEventError, StaleRevisionError
from aegis_persistence.unit_of_work import PostgresUnitOfWork

__all__ = [
    "DuplicateEventError",
    "PostgresUnitOfWork",
    "StaleRevisionError",
]
