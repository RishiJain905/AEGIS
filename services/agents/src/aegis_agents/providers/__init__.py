"""Agent provider wiring."""

from aegis_agents.providers.factory import create_generation_service
from aegis_agents.providers.generation import AgentGenerationFacade

__all__ = ["AgentGenerationFacade", "create_generation_service"]
